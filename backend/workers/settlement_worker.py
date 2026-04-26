from __future__ import annotations

import json
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
from backend.app.domain.pricing import closing_line_value
from backend.app.domain.settlement import SettlementDecision, normalize_match_status, settle_market_pick
from backend.app.domain.models import (
    ACTIVE_MATCH_STATUSES,
    SETTLED_MATCH_STATUSES,
)
from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.workers.metrics import store_metric


LOGGER = get_logger(__name__)
SETTLED_PICK_STATUSES = {"won", "lost", "push", "void"}
HOME_SCORE_CANDIDATES = ("home_score", "fthg")
AWAY_SCORE_CANDIDATES = ("away_score", "ftag")
MONEY_PRECISION = Decimal("0.0001")


def _log_worker_error(*, context: str, error: Exception, match_id: str | None = None) -> None:
    LOGGER.exception(
        json.dumps(
            {
                "event": "worker_failure",
                "worker": "settlement",
                "context": context,
                "source": "settlement",
                "league": None,
                "match_id": match_id,
                "error_type": type(error).__name__,
                "error": str(error),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )


@dataclass(frozen=True)
class SettlemablePick:
    pick_id: str
    match_id: str
    match_status: str
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    market: str
    selection: str
    offered_odds: Decimal
    stake_units: Decimal
    kickoff_at: datetime | None = None


def _target_date_from_env() -> date | None:
    raw_value = os.getenv("SETTLEMENT_WORKER_DATE", "").strip()
    if not raw_value:
        raw_shared_value = os.getenv("PIPELINE_DATE", "").strip() or os.getenv("WORKER_DATE", "").strip()
        if not raw_shared_value:
            return None
        raw_value = raw_shared_value
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
        "p.stake_units IS NOT NULL",
        "("
        "COALESCE(LOWER(p.status), 'open') <> ALL(%s) "
        "OR r.pick_id IS NULL "
        "OR COALESCE(LOWER(r.status), '') <> COALESCE(LOWER(p.status), 'open')"
        ")",
    ]
    params: list[object] = [list(SETTLED_MATCH_STATUSES), list(SETTLED_PICK_STATUSES)]
    if target_date is not None:
        filters.append("(m.kickoff_at AT TIME ZONE 'UTC')::date = %s")
        params.append(target_date)

    query = f"""
    SELECT
        p.id,
        p.match_id,
        m.status,
        m.kickoff_at,
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
    LEFT JOIN results r ON r.pick_id = p.id
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
            kickoff_at=row[3],
            match_status=str(row[2] or ""),
            home_team=str(row[4]),
            away_team=str(row[5]),
            home_score=int(row[6]) if row[6] is not None else None,
            away_score=int(row[7]) if row[7] is not None else None,
            market=str(row[8] or ""),
            selection=str(row[9] or ""),
            offered_odds=_normalize_decimal(row[10]),
            stake_units=_normalize_decimal(row[11]),
        )
        for row in rows
    ]


def _load_closing_odds(connection_factory, pick: SettlemablePick) -> Decimal | None:
    with connection_factory() as conn:
        with conn.cursor() as cursor:
            if pick.kickoff_at is not None:
                cursor.execute(
                    """
                    SELECT decimal_odds
                    FROM odds
                    WHERE match_id = %s
                      AND market = %s
                      AND selection = %s
                      AND captured_at <= %s
                    ORDER BY captured_at DESC
                    LIMIT 1
                    """,
                    (pick.match_id, pick.market, pick.selection, pick.kickoff_at),
                )
                row = cursor.fetchone()
                if row is not None and row[0] is not None:
                    return _normalize_decimal(row[0])

            cursor.execute(
                """
                SELECT decimal_odds
                FROM odds
                WHERE match_id = %s
                  AND market = %s
                  AND selection = %s
                ORDER BY captured_at DESC
                LIMIT 1
                """,
                (pick.match_id, pick.market, pick.selection),
            )
            row = cursor.fetchone()
    if row is None or row[0] is None:
        return None
    return _normalize_decimal(row[0])


def _count_incomplete_settlements(connection_factory, target_date: date | None) -> int:
    filters = [
        "LOWER(COALESCE(m.status, '')) = ANY(%s)",
        "p.stake_units IS NOT NULL",
        "("
        "COALESCE(LOWER(p.status), 'open') <> ALL(%s) "
        "OR r.pick_id IS NULL "
        "OR COALESCE(LOWER(r.status), '') <> COALESCE(LOWER(p.status), 'open')"
        ")",
    ]
    params: list[object] = [list(SETTLED_MATCH_STATUSES), list(SETTLED_PICK_STATUSES)]
    if target_date is not None:
        filters.append("(m.kickoff_at AT TIME ZONE 'UTC')::date = %s")
        params.append(target_date)

    query = f"""
    SELECT COUNT(*)
    FROM picks p
    JOIN matches m ON m.id = p.match_id
    LEFT JOIN results r ON r.pick_id = p.id
    WHERE {' AND '.join(filters)}
    """

    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
    return int(row[0]) if row else 0


def _settle_pick(pick: SettlemablePick) -> SettlementDecision | None:
    match_status = normalize_match_status(pick.match_status)
    if match_status not in SETTLED_MATCH_STATUSES:
        if match_status not in ACTIVE_MATCH_STATUSES:
            LOGGER.info(
                "Skipping settlement because match status is not settleable pick_id=%s match_id=%s status=%s",
                pick.pick_id,
                pick.match_id,
                pick.match_status,
            )
        return None
    return settle_market_pick(
        match_status=pick.match_status,
        home_team=pick.home_team,
        away_team=pick.away_team,
        home_score=pick.home_score,
        away_score=pick.away_score,
        market=pick.market,
        selection=pick.selection,
        stake_units=pick.stake_units,
        offered_odds=pick.offered_odds,
    )


def _persist_settlement(connection_factory, pick: SettlemablePick, decision: SettlementDecision) -> None:
    settled_at = datetime.now(timezone.utc)
    result_id = str(uuid4())
    closing_odds = _load_closing_odds(connection_factory, pick)
    clv_absolute = None
    clv_percent = None
    if closing_odds is not None:
        absolute, percent = closing_line_value(float(pick.offered_odds), float(closing_odds))
        clv_absolute = _normalize_decimal(absolute)
        clv_percent = Decimal(str(percent)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE picks
                SET status = %s,
                    closing_odds = %s,
                    clv_absolute = %s,
                    clv_percent = %s
                WHERE id = %s
                """,
                (decision.status, closing_odds, clv_absolute, clv_percent, pick.pick_id),
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
    pipeline_run_id = os.getenv("PIPELINE_RUN_ID", str(uuid4()))
    connection_factory = create_postgres_connection_factory()
    ensure_postgres_schema(connection_factory)
    incomplete_before = _count_incomplete_settlements(connection_factory, target_date)
    picks = _load_finished_picks(connection_factory, target_date)
    LOGGER.info(
        "Starting settlement worker target_date=%s picks=%s incomplete_before=%s",
        target_date.isoformat() if target_date else "all",
        len(picks),
        incomplete_before,
    )

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
    store_metric(
        connection_factory,
        metric_name="picks_settled",
        worker_name="settlement",
        pipeline_run_id=pipeline_run_id,
        target_date=target_date,
        metric_value=settled,
    )
    incomplete_after = _count_incomplete_settlements(connection_factory, target_date)
    if incomplete_after > 0:
        raise RuntimeError(
            "Settlement incomplete for "
            f"{incomplete_after} picks on target_date={target_date.isoformat() if target_date else 'all'}"
        )
    return settled


def main() -> int:
    configure_logging()
    try:
        run_once()
    except (psycopg2.Error, RuntimeError, ValueError) as exc:
        _log_worker_error(context="main", error=exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
