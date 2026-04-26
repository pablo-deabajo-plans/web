from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.domain.leagues import ESPN_INGESTION_LEAGUES
from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.services.match_ingestion import MatchIngestionService, MatchIngestionServiceError
from backend.workers.metrics import store_metric
from backend.workers.runtime import resolve_target_date


LOGGER = get_logger(__name__)
DEFAULT_HISTORY_MATCHES_PER_TEAM = 5


def _log_worker_error(*, source: str, league: str | None, match_id: str | None, context: str, error: Exception) -> None:
    LOGGER.exception(
        json.dumps(
            {
                "event": "worker_failure",
                "worker": "match_ingestion",
                "context": context,
                "source": source,
                "league": league,
                "match_id": match_id,
                "error_type": type(error).__name__,
                "error": str(error),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )


def _target_date_from_env() -> date:
    return resolve_target_date("MATCH_INGESTION_DATE")


def _selected_leagues() -> dict[str, dict[str, str]]:
    requested = os.getenv("MATCH_INGESTION_LEAGUES", "").strip()
    if not requested:
        return ESPN_INGESTION_LEAGUES

    selected_names = {item.strip() for item in requested.split(",") if item.strip()}
    return {
        league_name: config
        for league_name, config in ESPN_INGESTION_LEAGUES.items()
        if league_name in selected_names
    }


def _history_matches_per_team() -> int:
    raw_value = os.getenv("MATCH_HISTORY_BACKFILL_MATCHES_PER_TEAM", "").strip()
    if not raw_value:
        return DEFAULT_HISTORY_MATCHES_PER_TEAM
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("MATCH_HISTORY_BACKFILL_MATCHES_PER_TEAM must be an integer") from exc
    if value <= 0:
        raise ValueError("MATCH_HISTORY_BACKFILL_MATCHES_PER_TEAM must be greater than zero")
    return value


def run_once() -> int:
    target_date = _target_date_from_env()
    pipeline_run_id = os.getenv("PIPELINE_RUN_ID", str(uuid4()))
    leagues = _selected_leagues()
    history_matches_per_team = _history_matches_per_team()

    if not leagues:
        LOGGER.warning("No leagues selected for match ingestion")
        return 0

    connection_factory = create_postgres_connection_factory()
    ensure_postgres_schema(connection_factory)
    repository = PostgresMatchRepository(connection_factory)
    service = MatchIngestionService(repository=repository)

    total_persisted = 0
    failures: list[str] = []

    LOGGER.info(
        "Starting match ingestion cycle target_date=%s leagues=%s history_matches_per_team=%s",
        target_date.isoformat(),
        len(leagues),
        history_matches_per_team,
    )
    for competition, config in leagues.items():
        league_id = config["league_id"]
        season_type = config["season_type"]
        try:
            stored_matches = service.ingest_espn_matches_for_date(league_id, competition, target_date)
            teams_for_backfill = sorted(
                {
                    team
                    for match in stored_matches
                    for team in (match.home_team, match.away_team)
                    if team
                }
            )
            backfill_result = service.backfill_historical_matches(
                league_id,
                competition,
                season_type,
                target_date,
                team_names=teams_for_backfill,
                matches_per_team=history_matches_per_team,
            )
            total_persisted += len(stored_matches) + len(backfill_result.stored_matches)
            LOGGER.info(
                "Ingested matches competition=%s league_id=%s target_date=%s stored=%s backfilled=%s teams=%s season_type=%s",
                competition,
                league_id,
                target_date.isoformat(),
                len(stored_matches),
                len(backfill_result.stored_matches),
                len(backfill_result.requested_teams),
                season_type,
            )
        except MatchIngestionServiceError as exc:
            failures.append(competition)
            _log_worker_error(
                source="espn",
                league=competition,
                match_id=None,
                context=f"run_once league_id={league_id} target_date={target_date.isoformat()}",
                error=exc,
            )
        except (RuntimeError, ValueError) as exc:
            failures.append(competition)
            _log_worker_error(
                source="espn",
                league=competition,
                match_id=None,
                context=f"run_once_unexpected league_id={league_id} target_date={target_date.isoformat()}",
                error=exc,
            )

    LOGGER.info(
        "Finished match ingestion cycle target_date=%s total_persisted=%s failures=%s",
        target_date.isoformat(),
        total_persisted,
        len(failures),
    )
    store_metric(
        connection_factory,
        metric_name="matches_ingested",
        worker_name="match_ingestion",
        pipeline_run_id=pipeline_run_id,
        target_date=target_date,
        metric_value=total_persisted,
    )

    if failures:
        LOGGER.error("Leagues with ingestion failures: %s", ", ".join(failures))
        raise MatchIngestionServiceError(
            "Match ingestion failed for leagues: " + ", ".join(failures)
        )
    return total_persisted


def main() -> int:
    configure_logging()
    try:
        run_once()
    except (MatchIngestionServiceError, RuntimeError, ValueError) as exc:
        _log_worker_error(
            source="match_ingestion",
            league=None,
            match_id=None,
            context="main",
            error=exc,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
