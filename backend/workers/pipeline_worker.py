from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.domain.models import SETTLED_MATCH_STATUSES
from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.workers.analysis_worker import run_once as run_analysis_once
from backend.workers.match_ingestion_worker import run_once as run_match_ingestion_once
from backend.workers.odds_ingestion_worker import run_once as run_odds_ingestion_once
from backend.workers.runtime import resolve_target_date
from backend.workers.settlement_worker import run_once as run_settlement_once


LOGGER = get_logger(__name__)
PIPELINE_MATCH_STATUSES = ("scheduled", "live", "finished")


def _log_worker_error(*, context: str, error: Exception) -> None:
    LOGGER.exception(
        json.dumps(
            {
                "event": "worker_failure",
                "worker": "pipeline",
                "context": context,
                "source": "pipeline",
                "league": None,
                "match_id": None,
                "error_type": type(error).__name__,
                "error": str(error),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )


class PipelineWorkerError(RuntimeError):
    """Raised when the end-to-end worker pipeline cannot complete safely."""


@dataclass(frozen=True)
class PipelineSnapshot:
    matches_total: int
    matches_actionable: int
    finished_matches_total: int
    odds_quotes_total: int
    matches_with_supported_odds: int
    analyses_total: int
    picks_total: int
    settlement_eligible_picks_total: int
    settlement_completed_picks_total: int
    settlement_incomplete_picks_total: int
    results_total: int


def _target_date_from_env() -> date:
    return resolve_target_date("PIPELINE_DATE")


def _set_stage_dates(target_date: date) -> None:
    iso_date = target_date.isoformat()
    pipeline_run_id = str(uuid4())
    for env_name in (
        "PIPELINE_DATE",
        "WORKER_DATE",
        "MATCH_INGESTION_DATE",
        "ODDS_INGESTION_DATE",
        "ANALYSIS_WORKER_DATE",
        "SETTLEMENT_WORKER_DATE",
        "PIPELINE_RUN_ID",
    ):
        os.environ[env_name] = pipeline_run_id if env_name == "PIPELINE_RUN_ID" else iso_date


def _read_minimum(env_name: str, default: int) -> int:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{env_name} must be greater than or equal to zero")
    return value


def _ensure_schema(connection_factory) -> None:
    ensure_postgres_schema(connection_factory)


def _load_snapshot(connection_factory, target_date: date) -> PipelineSnapshot:
    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM matches
                WHERE (kickoff_at AT TIME ZONE 'UTC')::date = %s
                """,
                (target_date,),
            )
            matches_total = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM matches
                WHERE (kickoff_at AT TIME ZONE 'UTC')::date = %s
                  AND LOWER(COALESCE(status, '')) = ANY(%s)
                """,
                (target_date, list(PIPELINE_MATCH_STATUSES)),
            )
            matches_actionable = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM matches
                WHERE (kickoff_at AT TIME ZONE 'UTC')::date = %s
                  AND LOWER(COALESCE(status, '')) = ANY(%s)
                """,
                (target_date, list(SETTLED_MATCH_STATUSES)),
            )
            finished_matches_total = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM odds o
                JOIN matches m ON m.id = o.match_id
                WHERE (m.kickoff_at AT TIME ZONE 'UTC')::date = %s
                """,
                (target_date,),
            )
            odds_quotes_total = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(DISTINCT m.id)
                FROM matches m
                JOIN odds o ON o.match_id = m.id
                WHERE (m.kickoff_at AT TIME ZONE 'UTC')::date = %s
                  AND o.market IN ('1X2', 'BTTS', 'TOTAL_GOALS')
                """,
                (target_date,),
            )
            matches_with_supported_odds = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM analyses a
                JOIN matches m ON m.id = a.match_id
                WHERE (m.kickoff_at AT TIME ZONE 'UTC')::date = %s
                """,
                (target_date,),
            )
            analyses_total = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM picks p
                JOIN matches m ON m.id = p.match_id
                WHERE (m.kickoff_at AT TIME ZONE 'UTC')::date = %s
                """,
                (target_date,),
            )
            picks_total = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM picks p
                JOIN matches m ON m.id = p.match_id
                WHERE (m.kickoff_at AT TIME ZONE 'UTC')::date = %s
                  AND LOWER(COALESCE(m.status, '')) = ANY(%s)
                """,
                (target_date, list(SETTLED_MATCH_STATUSES)),
            )
            settlement_eligible_picks_total = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM picks p
                JOIN matches m ON m.id = p.match_id
                JOIN results r ON r.pick_id = p.id
                WHERE (m.kickoff_at AT TIME ZONE 'UTC')::date = %s
                  AND LOWER(COALESCE(m.status, '')) = ANY(%s)
                  AND COALESCE(LOWER(p.status), 'open') = ANY(%s)
                  AND COALESCE(LOWER(r.status), '') = COALESCE(LOWER(p.status), 'open')
                """,
                (target_date, list(SETTLED_MATCH_STATUSES), ["won", "lost", "push", "void"]),
            )
            settlement_completed_picks_total = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM picks p
                JOIN matches m ON m.id = p.match_id
                LEFT JOIN results r ON r.pick_id = p.id
                WHERE (m.kickoff_at AT TIME ZONE 'UTC')::date = %s
                  AND LOWER(COALESCE(m.status, '')) = ANY(%s)
                  AND p.stake_units IS NOT NULL
                  AND (
                      COALESCE(LOWER(p.status), 'open') <> ALL(%s)
                      OR r.pick_id IS NULL
                      OR COALESCE(LOWER(r.status), '') <> COALESCE(LOWER(p.status), 'open')
                  )
                """,
                (target_date, list(SETTLED_MATCH_STATUSES), ["won", "lost", "push", "void"]),
            )
            settlement_incomplete_picks_total = int(cursor.fetchone()[0])

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM results r
                JOIN picks p ON p.id = r.pick_id
                JOIN matches m ON m.id = p.match_id
                WHERE (m.kickoff_at AT TIME ZONE 'UTC')::date = %s
                """,
                (target_date,),
            )
            results_total = int(cursor.fetchone()[0])

    return PipelineSnapshot(
        matches_total=matches_total,
        matches_actionable=matches_actionable,
        finished_matches_total=finished_matches_total,
        odds_quotes_total=odds_quotes_total,
        matches_with_supported_odds=matches_with_supported_odds,
        analyses_total=analyses_total,
        picks_total=picks_total,
        settlement_eligible_picks_total=settlement_eligible_picks_total,
        settlement_completed_picks_total=settlement_completed_picks_total,
        settlement_incomplete_picks_total=settlement_incomplete_picks_total,
        results_total=results_total,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PipelineWorkerError(message)


def run_once() -> int:
    target_date = _target_date_from_env()
    _set_stage_dates(target_date)
    minimum_analyzed_matches = _read_minimum("PIPELINE_MIN_ANALYZED_MATCHES", 1)
    minimum_generated_picks = _read_minimum("PIPELINE_MIN_GENERATED_PICKS", 1)
    minimum_settlement_eligible_picks = _read_minimum("PIPELINE_MIN_SETTLEMENT_ELIGIBLE_PICKS", 1)

    connection_factory = create_postgres_connection_factory()
    LOGGER.info(
        "Starting pipeline worker target_date=%s min_analyzed_matches=%s min_generated_picks=%s min_settlement_eligible_picks=%s",
        target_date.isoformat(),
        minimum_analyzed_matches,
        minimum_generated_picks,
        minimum_settlement_eligible_picks,
    )

    _ensure_schema(connection_factory)
    run_match_ingestion_once()
    after_ingestion = _load_snapshot(connection_factory, target_date)
    _require(
        after_ingestion.matches_total > 0,
        f"Pipeline halted after match ingestion because no matches were stored for target_date={target_date.isoformat()}",
    )

    run_odds_ingestion_once()
    after_odds = _load_snapshot(connection_factory, target_date)
    _require(
        after_odds.matches_with_supported_odds > 0,
        f"Pipeline halted after odds ingestion because no supported odds were stored for target_date={target_date.isoformat()}",
    )

    run_analysis_once()
    after_analysis = _load_snapshot(connection_factory, target_date)
    _require(
        after_analysis.analyses_total >= minimum_analyzed_matches,
        (
            "Pipeline halted after analysis because analyzed_matches="
            f"{after_analysis.analyses_total} is below required minimum={minimum_analyzed_matches} "
            f"for target_date={target_date.isoformat()}"
        ),
    )
    _require(
        after_analysis.picks_total >= minimum_generated_picks,
        (
            "Pipeline halted after analysis because generated_picks="
            f"{after_analysis.picks_total} is below required minimum={minimum_generated_picks} "
            f"for target_date={target_date.isoformat()}"
        ),
    )

    run_settlement_once()
    final_snapshot = _load_snapshot(connection_factory, target_date)
    if final_snapshot.finished_matches_total > 0:
        _require(
            final_snapshot.settlement_eligible_picks_total >= minimum_settlement_eligible_picks,
            (
                "Pipeline halted after settlement because settlement_eligible_picks="
                f"{final_snapshot.settlement_eligible_picks_total} is below required minimum={minimum_settlement_eligible_picks} "
                f"while finished_matches={final_snapshot.finished_matches_total} "
                f"for target_date={target_date.isoformat()}"
            ),
        )
    if final_snapshot.settlement_eligible_picks_total > 0:
        _require(
            final_snapshot.settlement_incomplete_picks_total == 0,
            (
                "Pipeline halted after settlement because incomplete_settlements="
                f"{final_snapshot.settlement_incomplete_picks_total} remain for target_date={target_date.isoformat()}"
            ),
        )
        _require(
            final_snapshot.settlement_completed_picks_total >= final_snapshot.settlement_eligible_picks_total,
            (
                "Pipeline halted after settlement because completed_settlements="
                f"{final_snapshot.settlement_completed_picks_total} is below eligible_picks="
                f"{final_snapshot.settlement_eligible_picks_total} for target_date={target_date.isoformat()}"
            ),
        )
    LOGGER.info(
        "Finished pipeline worker target_date=%s matches=%s actionable_matches=%s finished_matches=%s odds_quotes=%s matches_with_supported_odds=%s analyses=%s picks=%s settlement_eligible_picks=%s settlement_completed_picks=%s settlement_incomplete_picks=%s results=%s",
        target_date.isoformat(),
        final_snapshot.matches_total,
        final_snapshot.matches_actionable,
        final_snapshot.finished_matches_total,
        final_snapshot.odds_quotes_total,
        final_snapshot.matches_with_supported_odds,
        final_snapshot.analyses_total,
        final_snapshot.picks_total,
        final_snapshot.settlement_eligible_picks_total,
        final_snapshot.settlement_completed_picks_total,
        final_snapshot.settlement_incomplete_picks_total,
        final_snapshot.results_total,
    )
    return final_snapshot.picks_total


def main() -> int:
    configure_logging()
    try:
        run_once()
    except (PipelineWorkerError, psycopg2.Error, RuntimeError, ValueError) as exc:
        _log_worker_error(context="main", error=exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
