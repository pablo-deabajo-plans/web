from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.domain.analysis import build_match_analysis
from backend.app.domain.pricing import build_pick
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.repositories.postgres.odds import PostgresOddsRepository
from backend.app.repositories.postgres.picks import PostgresPickRepository


LOGGER = get_logger(__name__)
MODEL_VERSION = "legacy-poisson-v1"

ANALYSIS_UPSERT_QUERY = """
INSERT INTO analyses (
    id,
    match_id,
    model_version,
    home_win_prob,
    draw_prob,
    away_win_prob,
    expected_home_goals,
    expected_away_goals,
    trace,
    generated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
ON CONFLICT (id) DO UPDATE SET
    home_win_prob = EXCLUDED.home_win_prob,
    draw_prob = EXCLUDED.draw_prob,
    away_win_prob = EXCLUDED.away_win_prob,
    expected_home_goals = EXCLUDED.expected_home_goals,
    expected_away_goals = EXCLUDED.expected_away_goals,
    trace = EXCLUDED.trace,
    generated_at = EXCLUDED.generated_at
"""

REQUIRED_ANALYSIS_COLUMNS = [
    "Date",
    "MatchDate",
    "Time",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
]

OPTIONAL_ANALYSIS_COLUMNS = ["HC", "AC", "HS", "AS", "HST", "AST", "HY", "AY", "HR", "AR"]

MARKET_QUOTE_RULES = [
    {"market_name": "1X2", "selection_name": "Home", "analysis_key": "1"},
    {"market_name": "1X2", "selection_name": "Draw", "analysis_key": "X"},
    {"market_name": "1X2", "selection_name": "Away", "analysis_key": "2"},
    {"market_name": "BTTS", "selection_name": "Yes", "analysis_key": "BTTS"},
    {"market_name": "TOTAL_GOALS", "selection_name": "Over 2.5", "analysis_key": "O25"},
]


def _target_date_from_env() -> date:
    raw_value = os.getenv("ANALYSIS_WORKER_DATE", "").strip()
    if not raw_value:
        return datetime.utcnow().date()
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("ANALYSIS_WORKER_DATE must use YYYY-MM-DD format") from exc


def _analysis_id(match_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"analysis:{MODEL_VERSION}:{match_id}"))


def _pick_id(match_id: str, market: str, selection: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"pick:{match_id}:{market}:{selection}:{MODEL_VERSION}"))


def _load_historical_frame(connection_factory, competition: str, target_date: date) -> pd.DataFrame:
    required_columns = list(REQUIRED_ANALYSIS_COLUMNS)
    optional_columns = list(OPTIONAL_ANALYSIS_COLUMNS)
    column_aliases = {
        "Date": None,
        "MatchDate": "MatchDate",
        "Time": "Time",
        "HomeTeam": "HomeTeam",
        "AwayTeam": "AwayTeam",
        "FTHG": "FTHG",
        "FTAG": "FTAG",
        "HC": "HC",
        "AC": "AC",
        "HS": "HS",
        "AS": "AS",
        "HST": "HST",
        "AST": "AST",
        "HY": "HY",
        "AY": "AY",
        "HR": "HR",
        "AR": "AR",
    }

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

            if "matchdate" in {column.lower() for column in available_columns}:
                column_aliases["MatchDate"] = next(column for column in available_columns if column.lower() == "matchdate")
            elif "kickoff_at" in available_columns:
                column_aliases["MatchDate"] = "kickoff_at"

            if "time" in {column.lower() for column in available_columns}:
                column_aliases["Time"] = next(column for column in available_columns if column.lower() == "time")
            elif "kickoff_at" in available_columns:
                column_aliases["Time"] = "kickoff_at"

            if "hometeam" in {column.lower() for column in available_columns}:
                column_aliases["HomeTeam"] = next(column for column in available_columns if column.lower() == "hometeam")
            elif "home_team" in available_columns:
                column_aliases["HomeTeam"] = "home_team"

            if "awayteam" in {column.lower() for column in available_columns}:
                column_aliases["AwayTeam"] = next(column for column in available_columns if column.lower() == "awayteam")
            elif "away_team" in available_columns:
                column_aliases["AwayTeam"] = "away_team"

            for stat_column in ["FTHG", "FTAG", "HC", "AC", "HS", "AS", "HST", "AST", "HY", "AY", "HR", "AR"]:
                lower_name = stat_column.lower()
                if lower_name in {column.lower() for column in available_columns}:
                    column_aliases[stat_column] = next(
                        column for column in available_columns if column.lower() == lower_name
                    )

            missing_required = [column for column in required_columns if column_aliases.get(column) is None]
            if missing_required:
                LOGGER.warning(
                    "Skipping analysis for competition=%s because matches table lacks required columns=%s",
                    competition,
                    ",".join(missing_required),
                )
                return pd.DataFrame(columns=required_columns + optional_columns + ["Source"])

            select_parts = []
            select_parts.append(
                "TO_CHAR(kickoff_at, 'DD/MM/YYYY') AS \"Date\"" if column_aliases["Date"] is None else f'"{column_aliases["Date"]}" AS "Date"'
            )
            select_parts.append(
                f'DATE("{column_aliases["MatchDate"]}") AS "MatchDate"'
                if column_aliases["MatchDate"] == "kickoff_at"
                else f'"{column_aliases["MatchDate"]}" AS "MatchDate"'
            )
            select_parts.append(
                f'TO_CHAR("{column_aliases["Time"]}", \'HH24:MI\') AS "Time"'
                if column_aliases["Time"] == "kickoff_at"
                else f'"{column_aliases["Time"]}" AS "Time"'
            )
            select_parts.append(f'"{column_aliases["HomeTeam"]}" AS "HomeTeam"')
            select_parts.append(f'"{column_aliases["AwayTeam"]}" AS "AwayTeam"')
            select_parts.append(f'"{column_aliases["FTHG"]}" AS "FTHG"')
            select_parts.append(f'"{column_aliases["FTAG"]}" AS "FTAG"')

            selected_optional = []
            for column in optional_columns:
                if column_aliases.get(column) is not None:
                    select_parts.append(f'"{column_aliases[column]}" AS "{column}"')
                    selected_optional.append(column)

            select_clause = ", ".join(select_parts)
            selected_columns = required_columns + selected_optional
            query = f"""
            SELECT {select_clause}
            FROM matches
            WHERE competition = %s
              AND DATE(kickoff_at) < %s
              AND "{column_aliases["FTHG"]}" IS NOT NULL
              AND "{column_aliases["FTAG"]}" IS NOT NULL
            ORDER BY kickoff_at ASC
            """
            cursor.execute(query, (competition, target_date))
            rows = cursor.fetchall()

    if not rows:
        return pd.DataFrame(columns=required_columns + optional_columns + ["Source"])

    frame = pd.DataFrame(rows, columns=selected_columns)
    for column in optional_columns:
        if column not in frame.columns:
            frame[column] = None
    frame["Source"] = "DB"
    return frame


def _store_analysis(connection_factory, match_id: str, analysis: dict) -> str:
    analysis_id = _analysis_id(match_id)
    generated_at = datetime.utcnow()
    payload = (
        analysis_id,
        match_id,
        MODEL_VERSION,
        analysis["resultado"]["1"],
        analysis["resultado"]["X"],
        analysis["resultado"]["2"],
        analysis["xg_local"],
        analysis["xg_visitante"],
        json.dumps(analysis["trace"], ensure_ascii=True),
        generated_at,
    )

    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(ANALYSIS_UPSERT_QUERY, payload)
        conn.commit()
    return analysis_id


def _normalize_market_name(selection_name: str, home_team: str, away_team: str) -> str:
    if selection_name == home_team:
        return "Home"
    if selection_name == away_team:
        return "Away"
    if selection_name in {"Empate", "X"}:
        return "Draw"
    return selection_name


def _quote_index(quotes, home_team: str, away_team: str) -> dict[tuple[str, str], object]:
    indexed = {}
    for quote in quotes:
        market_name = str(quote.market or "").strip().upper()
        selection_name = _normalize_market_name(str(quote.selection or "").strip(), home_team, away_team)
        indexed[(market_name, selection_name)] = quote
    return indexed


def _build_picks_for_analysis(match, analysis: dict, quotes) -> list:
    quote_lookup = _quote_index(quotes, match.home_team, match.away_team)
    picks = []

    market_name_map = {
        "Victoria " + analysis["local"]: ("1X2", "Home"),
        "Empate": ("1X2", "Draw"),
        "Victoria " + analysis["visitante"]: ("1X2", "Away"),
        "Ambos marcan": ("BTTS", "Yes"),
        "Over 2.5 goles": ("TOTAL_GOALS", "Over 2.5"),
    }

    for market in analysis.get("mercados", []):
        mapping = market_name_map.get(market["nombre"])
        if mapping is None:
            continue
        quote = quote_lookup.get(mapping)
        if quote is None:
            continue

        pick = build_pick(
            pick_id=_pick_id(match.id, market["nombre"], market["nombre"]),
            match_id=match.id,
            market=market["nombre"],
            selection=market["nombre"],
            probability=float(market["prob"]),
            offered_odds=float(quote.decimal_odds),
            provider=quote.sportsbook,
        )
        if pick.edge <= 0:
            continue
        picks.append(pick)
    return picks


def run_once() -> int:
    target_date = _target_date_from_env()
    connection_factory = create_postgres_connection_factory()
    match_repository = PostgresMatchRepository(connection_factory)
    odds_repository = PostgresOddsRepository(connection_factory)
    pick_repository = PostgresPickRepository(connection_factory)

    matches = list(match_repository.list_matches_for_day(target_date))
    LOGGER.info("Starting analysis worker target_date=%s matches=%s", target_date.isoformat(), len(matches))

    stored_picks = 0
    analyzed_matches = 0
    skipped_matches = 0

    for match in matches:
        historical_frame = _load_historical_frame(connection_factory, match.competition, target_date)
        if historical_frame.empty:
            skipped_matches += 1
            LOGGER.warning(
                "Skipping match analysis due to missing historical dataset match_id=%s competition=%s",
                match.id,
                match.competition,
            )
            continue

        analysis = build_match_analysis(
            historical_frame,
            match.competition,
            match.home_team,
            match.away_team,
            match_date=match.kickoff_at.date(),
            match_label=f"{match.kickoff_at.isoformat()} | {match.home_team} vs {match.away_team}",
        )
        if analysis is None:
            skipped_matches += 1
            LOGGER.warning("Analysis returned no result for match_id=%s", match.id)
            continue

        _store_analysis(connection_factory, match.id, analysis)
        analyzed_matches += 1

        quotes = list(odds_repository.list_odds_for_match(match.id))
        picks = _build_picks_for_analysis(match, analysis, quotes)
        for pick in picks:
            pick_repository.save_pick(pick)
            stored_picks += 1

        LOGGER.info(
            "Analyzed match match_id=%s competition=%s quotes=%s picks_saved=%s",
            match.id,
            match.competition,
            len(quotes),
            len(picks),
        )

    LOGGER.info(
        "Finished analysis worker target_date=%s analyzed_matches=%s skipped_matches=%s picks_saved=%s",
        target_date.isoformat(),
        analyzed_matches,
        skipped_matches,
        stored_picks,
    )
    return stored_picks


def main() -> int:
    configure_logging()
    try:
        run_once()
    except Exception:
        LOGGER.exception("Analysis worker crashed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
