from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.core.time import utc_now
from backend.app.domain.analysis import build_match_analysis
from backend.app.domain.models import Analysis
from backend.app.domain.pick_generation import (
    MODEL_VERSION,
    analysis_id_for_match,
    build_picks_for_analysis,
)
from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.repositories.postgres.odds import PostgresOddsRepository
from backend.app.repositories.postgres.picks import PostgresPickRepository
from backend.workers.metrics import store_metric
from backend.workers.runtime import resolve_target_date


LOGGER = get_logger(__name__)
ANALYZABLE_MATCH_STATUSES = {"scheduled", "live"}
SKIP_CATEGORIES = ("missing_history", "missing_odds", "insufficient_data", "non_actionable")

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

REQUIRED_ANALYSIS_COLUMNS = ["Date", "MatchDate", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]

OPTIONAL_ANALYSIS_COLUMNS = ["HC", "AC", "HS", "AS", "HST", "AST", "HY", "AY", "HR", "AR"]

def _target_date_from_env() -> date:
    return resolve_target_date("ANALYSIS_WORKER_DATE")


def _analysis_id(match_id: str) -> str:
    return analysis_id_for_match(match_id, MODEL_VERSION)


def _normalize_match_status(value: str | None) -> str:
    return str(value or "").strip().lower()


def _is_match_ready_for_analysis(match) -> bool:
    if not match.id or not match.home_team or not match.away_team or match.kickoff_at is None:
        return False
    return _normalize_match_status(match.status) in ANALYZABLE_MATCH_STATUSES


def _load_historical_frame(connection_factory, competition: str, target_date: date) -> pd.DataFrame:
    required_columns = list(REQUIRED_ANALYSIS_COLUMNS)
    optional_columns = list(OPTIONAL_ANALYSIS_COLUMNS)
    column_candidates = {
        "MatchDate": ["matchdate", "kickoff_at"],
        "Time": ["time", "kickoff_at"],
        "HomeTeam": ["hometeam", "home_team"],
        "AwayTeam": ["awayteam", "away_team"],
        "FTHG": ["fthg", "home_score"],
        "FTAG": ["ftag", "away_score"],
        "HC": ["hc", "home_corners"],
        "AC": ["ac", "away_corners"],
        "HS": ["hs", "home_shots"],
        "AS": ["as", "away_shots"],
        "HST": ["hst", "home_shots_on_target"],
        "AST": ["ast", "away_shots_on_target"],
        "HY": ["hy"],
        "AY": ["ay"],
        "HR": ["hr"],
        "AR": ["ar"],
    }
    column_aliases = {"Date": None}

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

            available_lower = {column.lower(): column for column in available_columns}
            for logical_name, candidates in column_candidates.items():
                column_aliases[logical_name] = next(
                    (available_lower[candidate] for candidate in candidates if candidate in available_lower),
                    None,
                )

            missing_required = [
                column
                for column in required_columns
                if column != "Date" and column_aliases.get(column) is None
            ]
            if missing_required:
                LOGGER.warning(
                    "Skipping analysis for competition=%s because matches table lacks required columns=%s",
                    competition,
                    ",".join(missing_required),
                )
                return pd.DataFrame(columns=required_columns + optional_columns + ["Source"])

            select_parts = []
            select_parts.append(
                "TO_CHAR(kickoff_at AT TIME ZONE 'UTC', 'DD/MM/YYYY') AS \"Date\"" if column_aliases["Date"] is None else f'"{column_aliases["Date"]}" AS "Date"'
            )
            select_parts.append(
                f'("{column_aliases["MatchDate"]}" AT TIME ZONE \'UTC\')::date AS "MatchDate"'
                if column_aliases["MatchDate"] == "kickoff_at"
                else f'"{column_aliases["MatchDate"]}" AS "MatchDate"'
            )
            select_parts.append(
                f'TO_CHAR("{column_aliases["Time"]}" AT TIME ZONE \'UTC\', \'HH24:MI\') AS "Time"'
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
              AND (kickoff_at AT TIME ZONE 'UTC')::date < %s
              AND LOWER(COALESCE(status, '')) = 'finished'
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


def _store_analysis(connection_factory, match_id: str, analysis: Analysis) -> str:
    analysis_id = _analysis_id(match_id)
    generated_at = utc_now()
    payload = (
        analysis_id,
        match_id,
        MODEL_VERSION,
        analysis.resultado.home_win,
        analysis.resultado.draw,
        analysis.resultado.away_win,
        analysis.xg_local,
        analysis.xg_visitante,
        json.dumps(analysis.trace, ensure_ascii=True),
        generated_at,
    )

    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(ANALYSIS_UPSERT_QUERY, payload)
        conn.commit()
    return analysis_id


def _log_skip(match, category: str, *, detail: str, **context) -> None:
    payload = {
        "event": "analysis_skip",
        "category": category,
        "match_id": getattr(match, "id", None),
        "competition": getattr(match, "competition", None),
        "status": getattr(match, "status", None),
        "detail": detail,
    }
    payload.update(context)
    LOGGER.info(json.dumps(payload, ensure_ascii=True, sort_keys=True))


def run_once() -> int:
    target_date = _target_date_from_env()
    pipeline_run_id = os.getenv("PIPELINE_RUN_ID", str(uuid4()))
    connection_factory = create_postgres_connection_factory()
    ensure_postgres_schema(connection_factory)
    match_repository = PostgresMatchRepository(connection_factory)
    odds_repository = PostgresOddsRepository(connection_factory)
    pick_repository = PostgresPickRepository(connection_factory)

    matches = list(match_repository.list_matches_for_day(target_date))
    LOGGER.info("Starting analysis worker target_date=%s matches=%s", target_date.isoformat(), len(matches))

    stored_picks = 0
    analyzed_matches = 0
    skipped_matches = 0
    historical_frames: dict[str, pd.DataFrame] = {}
    skip_counters = {category: 0 for category in SKIP_CATEGORIES}

    for match in matches:
        if not _is_match_ready_for_analysis(match):
            skipped_matches += 1
            skip_counters["non_actionable"] += 1
            _log_skip(
                match,
                "non_actionable",
                detail="match_not_ready",
            )
            continue

        historical_frame = historical_frames.get(match.competition)
        if historical_frame is None:
            historical_frame = _load_historical_frame(connection_factory, match.competition, target_date)
            historical_frames[match.competition] = historical_frame
        if historical_frame.empty:
            skipped_matches += 1
            skip_counters["missing_history"] += 1
            _log_skip(
                match,
                "missing_history",
                detail="historical_frame_empty",
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
            skip_counters["insufficient_data"] += 1
            _log_skip(
                match,
                "insufficient_data",
                detail="analysis_returned_none",
            )
            continue

        analysis_id = _store_analysis(connection_factory, match.id, analysis)
        analyzed_matches += 1

        quotes = list(odds_repository.list_odds_for_match(match.id))
        if not quotes:
            skipped_matches += 1
            skip_counters["missing_odds"] += 1
            _log_skip(
                match,
                "missing_odds",
                detail="stored_odds_missing",
            )
            continue

        picks, skip_category = build_picks_for_analysis(match, analysis, analysis_id, quotes)
        if not picks:
            skipped_matches += 1
            categorized_skip = skip_category or "insufficient_data"
            skip_counters[categorized_skip] += 1
            _log_skip(
                match,
                categorized_skip,
                detail="pick_generation_skipped",
                quotes=len(quotes),
            )
            continue

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
        json.dumps(
            {
                "event": "analysis_summary",
                "target_date": target_date.isoformat(),
                "analyzed_matches": analyzed_matches,
                "skipped_matches": skipped_matches,
                "picks_saved": stored_picks,
                "skip_counters": skip_counters,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    store_metric(
        connection_factory,
        metric_name="matches_analyzed",
        worker_name="analysis",
        pipeline_run_id=pipeline_run_id,
        target_date=target_date,
        metric_value=analyzed_matches,
    )
    store_metric(
        connection_factory,
        metric_name="picks_generated",
        worker_name="analysis",
        pipeline_run_id=pipeline_run_id,
        target_date=target_date,
        metric_value=stored_picks,
    )
    store_metric(
        connection_factory,
        metric_name="analysis_skipped_by_reason",
        worker_name="analysis",
        pipeline_run_id=pipeline_run_id,
        target_date=target_date,
        json_value=json.dumps(skip_counters, ensure_ascii=True, sort_keys=True),
    )
    return stored_picks


def main() -> int:
    configure_logging()
    try:
        run_once()
    except (RuntimeError, ValueError) as exc:
        LOGGER.exception(
            json.dumps(
                {
                    "event": "worker_failure",
                    "worker": "analysis",
                    "context": "main",
                    "source": "analysis",
                    "league": None,
                    "match_id": None,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
