from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.repositories.postgres.connection import create_postgres_connection_factory


LOGGER = get_logger(__name__)
SETTLED_PICK_STATUSES = {"won", "lost", "push", "void"}
FINISHED_MATCH_STATUSES = {"completed", "finished", "final", "full_time", "full-time", "post", "closed"}
HOME_SCORE_CANDIDATES = ("home_score", "fthg")
AWAY_SCORE_CANDIDATES = ("away_score", "ftag")
MONEY_PRECISION = Decimal("0.0001")


@dataclass(frozen=True)
class SettlemablePick:
    pick_id: str
    match_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    market: str
    selection: str
    offered_odds: Decimal
    stake_units: Decimal


@dataclass(frozen=True)
class SettlementDecision:
    status: str
    settled_selection: str
    profit_units: Decimal


def _target_date_from_env() -> date | None:
    raw_value = os.getenv("SETTLEMENT_WORKER_DATE", "").strip()
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("SETTLEMENT_WORKER_DATE must use YYYY-MM-DD format") from exc


def _normalize_decimal(value: object) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _column_lookup(column_names: set[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {column.lower(): column for column in column_names}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _score_columns(connection_factory) -> tuple[str, str]:
    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'matches'
                """
            )
            available_columns = {row[0] for row in cursor.fetchall()}

    home_score_column = _column_lookup(available_columns, HOME_SCORE_CANDIDATES)
    away_score_column = _column_lookup(available_columns, AWAY_SCORE_CANDIDATES)
    if home_score_column is None or away_score_column is None:
        raise RuntimeError("Matches table must expose score columns for settlement")
    return home_score_column, away_score_column


def _load_finished_picks(connection_factory, target_date: date | None) -> list[SettlemablePick]:
    home_score_column, away_score_column = _score_columns(connection_factory)
    filters = [
        "LOWER(COALESCE(m.status, '')) = ANY(%s)",
        f'm."{home_score_column}" IS NOT NULL',
        f'm."{away_score_column}" IS NOT NULL',
        "p.stake_units IS NOT NULL",
        "COALESCE(LOWER(p.status), 'open') <> ALL(%s)",
    ]
    params: list[object] = [list(FINISHED_MATCH_STATUSES), list(SETTLED_PICK_STATUSES)]
    if target_date is not None:
        filters.append("DATE(m.kickoff_at) = %s")
        params.append(target_date)

    query = f"""
    SELECT
        p.id,
        p.match_id,
        m.home_team,
        m.away_team,
        m."{home_score_column}" AS home_score,
        m."{away_score_column}" AS away_score,
        p.market,
        p.selection,
        p.offered_odds,
        p.stake_units
    FROM picks p
    JOIN matches m ON m.id = p.match_id
    WHERE {' AND '.join(filters)}
    ORDER BY m.kickoff_at ASC, p.created_at ASC
    """

    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        SettlemablePick(
            pick_id=str(row[0]),
            match_id=str(row[1]),
            home_team=str(row[2]),
            away_team=str(row[3]),
            home_score=int(row[4]),
            away_score=int(row[5]),
            market=str(row[6] or ""),
            selection=str(row[7] or ""),
            offered_odds=_normalize_decimal(row[8]),
            stake_units=_normalize_decimal(row[9]),
        )
        for row in rows
    ]


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalize_1x2_selection(selection: str, home_team: str, away_team: str) -> str:
    normalized = _normalize_text(selection)
    if normalized in {"home", _normalize_text(home_team), _normalize_text(f"victoria {home_team}")}:
        return "home"
    if normalized in {"away", _normalize_text(away_team), _normalize_text(f"victoria {away_team}")}:
        return "away"
    if normalized in {"draw", "x", "empate"}:
        return "draw"
    return normalized


def _parse_total_points(selection: str, market: str) -> tuple[str, Decimal] | None:
    candidate = _normalize_text(f"{market} {selection}")
    direction = None
    if "over" in candidate:
        direction = "over"
    elif "under" in candidate:
        direction = "under"
    if direction is None:
        return None

    for token in candidate.replace(",", ".").split():
        try:
            return direction, Decimal(token)
        except Exception:
            continue
    return None


def _settled_selection_1x2(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def _profit_for_status(status: str, stake_units: Decimal, offered_odds: Decimal) -> Decimal:
    if status == "won":
        return (stake_units * (offered_odds - Decimal("1"))).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)
    if status == "push":
        return Decimal("0.0000")
    return (stake_units * Decimal("-1")).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _settle_pick(pick: SettlemablePick) -> SettlementDecision | None:
    total_goals = pick.home_score + pick.away_score
    market_key = _normalize_text(pick.market)
    selection_key = _normalize_text(pick.selection)

    if market_key == "1x2" or selection_key in {"home", "away", "draw", "x", "empate"}:
        settled_selection = _settled_selection_1x2(pick.home_score, pick.away_score)
        selected = _normalize_1x2_selection(pick.selection, pick.home_team, pick.away_team)
        status = "won" if selected == settled_selection else "lost"
        return SettlementDecision(
            status=status,
            settled_selection=settled_selection,
            profit_units=_profit_for_status(status, pick.stake_units, pick.offered_odds),
        )

    if market_key.startswith("victoria ") or selection_key.startswith("victoria "):
        settled_selection = _settled_selection_1x2(pick.home_score, pick.away_score)
        selected = _normalize_1x2_selection(pick.selection or pick.market, pick.home_team, pick.away_team)
        status = "won" if selected == settled_selection else "lost"
        return SettlementDecision(
            status=status,
            settled_selection=settled_selection,
            profit_units=_profit_for_status(status, pick.stake_units, pick.offered_odds),
        )

    if market_key == "btts" or market_key == "ambos marcan" or selection_key in {"yes", "no", "ambos marcan"}:
        both_teams_scored = pick.home_score > 0 and pick.away_score > 0
        settled_selection = "yes" if both_teams_scored else "no"
        selected = "yes" if selection_key in {"yes", "ambos marcan"} else "no"
        status = "won" if selected == settled_selection else "lost"
        return SettlementDecision(
            status=status,
            settled_selection=settled_selection,
            profit_units=_profit_for_status(status, pick.stake_units, pick.offered_odds),
        )

    total_market = _parse_total_points(pick.selection, pick.market)
    if total_market is not None:
        direction, line = total_market
        total_goals_decimal = Decimal(total_goals)
        if total_goals_decimal == line:
            status = "push"
        elif direction == "over":
            status = "won" if total_goals_decimal > line else "lost"
        else:
            status = "won" if total_goals_decimal < line else "lost"
        return SettlementDecision(
            status=status,
            settled_selection=f"{direction} {line.normalize()}",
            profit_units=_profit_for_status(status, pick.stake_units, pick.offered_odds),
        )

    LOGGER.warning(
        "Skipping unsupported market for settlement pick_id=%s market=%s selection=%s",
        pick.pick_id,
        pick.market,
        pick.selection,
    )
    return None


def _persist_settlement(connection_factory, pick: SettlemablePick, decision: SettlementDecision) -> None:
    settled_at = datetime.now(timezone.utc)
    result_id = str(uuid4())
    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE picks
                SET status = %s
                WHERE id = %s
                """,
                (decision.status, pick.pick_id),
            )
            cursor.execute(
                """
                INSERT INTO results (id, pick_id, status, settled_selection, stake_units, profit_units, settled_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (pick_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    settled_selection = EXCLUDED.settled_selection,
                    stake_units = EXCLUDED.stake_units,
                    profit_units = EXCLUDED.profit_units,
                    settled_at = EXCLUDED.settled_at
                """,
                (
                    result_id,
                    pick.pick_id,
                    decision.status,
                    decision.settled_selection,
                    pick.stake_units,
                    decision.profit_units,
                    settled_at,
                ),
            )
        conn.commit()


def run_once() -> int:
    target_date = _target_date_from_env()
    connection_factory = create_postgres_connection_factory()
    picks = _load_finished_picks(connection_factory, target_date)
    LOGGER.info("Starting settlement worker target_date=%s picks=%s", target_date.isoformat() if target_date else "all", len(picks))

    settled = 0
    skipped = 0
    for pick in picks:
        decision = _settle_pick(pick)
        if decision is None:
            skipped += 1
            continue
        _persist_settlement(connection_factory, pick, decision)
        settled += 1

    LOGGER.info(
        "Finished settlement worker target_date=%s settled=%s skipped=%s",
        target_date.isoformat() if target_date else "all",
        settled,
        skipped,
    )
    return settled


def main() -> int:
    configure_logging()
    try:
        run_once()
    except (psycopg2.Error, RuntimeError, ValueError):
        LOGGER.exception("Settlement worker crashed")
        return 1
    except Exception:
        LOGGER.exception("Unexpected settlement worker crash")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
