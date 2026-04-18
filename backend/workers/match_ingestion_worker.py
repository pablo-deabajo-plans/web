from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.services.match_ingestion import MatchIngestionService, MatchIngestionServiceError


LOGGER = get_logger(__name__)
LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")

ESPN_INGESTION_LEAGUES: dict[str, dict[str, str]] = {
    "Premier League": {"league_id": "eng.1", "season_type": "calendar"},
    "League One": {"league_id": "eng.3", "season_type": "calendar"},
    "League Two": {"league_id": "eng.4", "season_type": "calendar"},
    "Escocia Premiership": {"league_id": "sco.1", "season_type": "calendar"},
    "Escocia Championship": {"league_id": "sco.2", "season_type": "calendar"},
    "Escocia League One": {"league_id": "sco.3", "season_type": "calendar"},
    "Escocia League Two": {"league_id": "sco.4", "season_type": "calendar"},
    "LaLiga": {"league_id": "esp.1", "season_type": "calendar"},
    "Segunda Division": {"league_id": "esp.2", "season_type": "calendar"},
    "Serie A": {"league_id": "ita.1", "season_type": "calendar"},
    "Serie B": {"league_id": "ita.2", "season_type": "calendar"},
    "Bundesliga": {"league_id": "ger.1", "season_type": "calendar"},
    "Ligue 1": {"league_id": "fra.1", "season_type": "calendar"},
    "Ligue 2": {"league_id": "fra.2", "season_type": "calendar"},
    "Holanda": {"league_id": "ned.1", "season_type": "calendar"},
    "Belgica": {"league_id": "bel.1", "season_type": "calendar"},
    "Liga de Portugal": {"league_id": "por.1", "season_type": "calendar"},
    "Grecia": {"league_id": "gre.1", "season_type": "calendar"},
    "Turquia": {"league_id": "tur.1", "season_type": "calendar"},
    "Segunda Inglesa": {"league_id": "eng.2", "season_type": "calendar"},
    "Arabia Saudi": {"league_id": "ksa.1", "season_type": "european"},
    "Australia": {"league_id": "aus.1", "season_type": "australia"},
    "Internacionales": {"league_id": "fifa.friendly", "season_type": "calendar"},
    "Segunda Alemana": {"league_id": "ger.2", "season_type": "calendar"},
    "Chile": {"league_id": "chi.1", "season_type": "calendar"},
    "MLS": {"league_id": "usa.1", "season_type": "calendar"},
    "Champions League": {"league_id": "uefa.champions", "season_type": "european"},
    "Europa League": {"league_id": "uefa.europa", "season_type": "european"},
    "Conference League": {"league_id": "uefa.europa.conf", "season_type": "european"},
    "Copa del Rey": {"league_id": "esp.copa_del_rey", "season_type": "european"},
    "WSL Femenina": {"league_id": "eng.w.1", "season_type": "european"},
    "Liga F": {"league_id": "esp.w.1", "season_type": "european"},
    "Premiere Ligue Femenina": {"league_id": "fra.w.1", "season_type": "european"},
}


def _target_date_from_env() -> date:
    raw_value = os.getenv("MATCH_INGESTION_DATE", "").strip()
    if not raw_value:
        return datetime.now(LOCAL_TIMEZONE).date()
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("MATCH_INGESTION_DATE must use YYYY-MM-DD format") from exc


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


def run_once() -> int:
    target_date = _target_date_from_env()
    leagues = _selected_leagues()

    if not leagues:
        LOGGER.warning("No leagues selected for match ingestion")
        return 0

    connection_factory = create_postgres_connection_factory()
    repository = PostgresMatchRepository(connection_factory)
    service = MatchIngestionService(repository=repository)

    total_persisted = 0
    failures: list[str] = []

    LOGGER.info("Starting match ingestion cycle target_date=%s leagues=%s", target_date.isoformat(), len(leagues))
    for competition, config in leagues.items():
        league_id = config["league_id"]
        season_type = config["season_type"]
        try:
            stored_matches = service.ingest_espn_matches_for_date(league_id, competition, target_date)
            total_persisted += len(stored_matches)
            LOGGER.info(
                "Ingested matches competition=%s league_id=%s target_date=%s stored=%s season_type=%s",
                competition,
                league_id,
                target_date.isoformat(),
                len(stored_matches),
                season_type,
            )
        except MatchIngestionServiceError:
            failures.append(competition)
            LOGGER.exception(
                "Match ingestion failed competition=%s league_id=%s target_date=%s",
                competition,
                league_id,
                target_date.isoformat(),
            )
        except Exception:
            failures.append(competition)
            LOGGER.exception(
                "Unexpected match ingestion failure competition=%s league_id=%s target_date=%s",
                competition,
                league_id,
                target_date.isoformat(),
            )

    LOGGER.info(
        "Finished match ingestion cycle target_date=%s total_persisted=%s failures=%s",
        target_date.isoformat(),
        total_persisted,
        len(failures),
    )

    if failures:
        LOGGER.warning("Leagues with ingestion failures: %s", ", ".join(failures))
    return total_persisted


def main() -> int:
    configure_logging()
    try:
        run_once()
    except Exception:
        LOGGER.exception("Match ingestion worker crashed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
