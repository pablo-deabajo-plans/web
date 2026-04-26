from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.domain.leagues import ESPN_INGESTION_LEAGUES
from backend.app.domain.models import OddsQuote
from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.repositories.postgres.odds import PostgresOddsRepository
from backend.app.repositories.providers.espn import ESPNProviderError, extract_supported_odds, request_espn_summary
from backend.workers.metrics import store_metric
from backend.workers.runtime import resolve_target_date


LOGGER = get_logger(__name__)
SKIP_CATEGORIES = ("missing_history", "missing_odds", "insufficient_data", "non_actionable")


def _log_worker_error(*, source: str, league: str | None, match_id: str | None, context: str, error: Exception) -> None:
    LOGGER.exception(
        json.dumps(
            {
                "event": "worker_failure",
                "worker": "odds_ingestion",
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
    return resolve_target_date("ODDS_INGESTION_DATE")


def _selected_leagues() -> dict[str, dict[str, str]]:
    requested = os.getenv("ODDS_INGESTION_LEAGUES", "").strip()
    if not requested:
        return ESPN_INGESTION_LEAGUES

    selected_names = {item.strip() for item in requested.split(",") if item.strip()}
    return {
        league_name: config
        for league_name, config in ESPN_INGESTION_LEAGUES.items()
        if league_name in selected_names
    }


def _snapshot_id(match_id: str, market: str, selection: str, sportsbook: str | None, captured_at: datetime) -> str:
    provider_name = str(sportsbook or "ESPN").strip() or "ESPN"
    return str(uuid5(NAMESPACE_URL, f"odds:{match_id}:{market}:{selection}:{provider_name}:{captured_at.isoformat()}"))


def _build_quotes(match_id: str, summary: dict) -> list[OddsQuote]:
    quotes: list[OddsQuote] = []
    for snapshot in extract_supported_odds(summary):
        captured_at = snapshot["captured_at"]
        quote = OddsQuote(
            id=_snapshot_id(
                match_id,
                str(snapshot["market"]),
                str(snapshot["selection"]),
                snapshot.get("sportsbook"),
                captured_at,
            ),
            match_id=match_id,
            market=str(snapshot["market"]),
            selection=str(snapshot["selection"]),
            decimal_odds=float(snapshot["decimal_odds"]),
            sportsbook=str(snapshot.get("sportsbook") or "ESPN"),
            captured_at=captured_at,
        )
        quotes.append(quote)
    return quotes


def _log_skip(match, category: str, *, detail: str, **context) -> None:
    payload = {
        "event": "odds_ingestion_skip",
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
    selected_leagues = _selected_leagues()
    if not selected_leagues:
        LOGGER.warning("No leagues selected for odds ingestion")
        return 0

    connection_factory = create_postgres_connection_factory()
    ensure_postgres_schema(connection_factory)
    match_repository = PostgresMatchRepository(connection_factory)
    odds_repository = PostgresOddsRepository(connection_factory)
    matches = list(match_repository.list_matches_for_day(target_date))

    persisted_quotes = 0
    matches_with_odds = 0
    skipped_matches = 0
    failures: list[str] = []
    skip_counters = {category: 0 for category in SKIP_CATEGORIES}

    LOGGER.info("Starting odds ingestion target_date=%s matches=%s", target_date.isoformat(), len(matches))

    for match in matches:
        league_config = selected_leagues.get(match.competition)
        if league_config is None:
            skipped_matches += 1
            skip_counters["non_actionable"] += 1
            _log_skip(
                match,
                "non_actionable",
                detail="unsupported_competition",
            )
            continue
        if not match.external_id:
            skipped_matches += 1
            skip_counters["insufficient_data"] += 1
            _log_skip(
                match,
                "insufficient_data",
                detail="missing_external_id",
            )
            continue

        league_id = league_config["league_id"]
        try:
            summary = request_espn_summary(league_id, match.external_id, timeout=20)
            quotes = _build_quotes(match.id, summary)
        except ESPNProviderError as exc:
            skipped_matches += 1
            failures.append(str(match.id))
            _log_worker_error(
                source="espn",
                league=match.competition,
                match_id=match.id,
                context=f"request_summary external_id={match.external_id}",
                error=exc,
            )
            continue
        except (RuntimeError, ValueError) as exc:
            skipped_matches += 1
            failures.append(str(match.id))
            _log_worker_error(
                source="espn",
                league=match.competition,
                match_id=match.id,
                context=f"build_quotes external_id={match.external_id}",
                error=exc,
            )
            continue

        if not quotes:
            skipped_matches += 1
            skip_counters["missing_odds"] += 1
            _log_skip(
                match,
                "missing_odds",
                detail="provider_returned_no_supported_odds",
            )
            continue

        odds_repository.upsert_odds(quotes)
        persisted_quotes += len(quotes)
        matches_with_odds += 1

        LOGGER.info(
            "Stored odds snapshots match_id=%s competition=%s quotes=%s",
            match.id,
            match.competition,
            len(quotes),
        )

    LOGGER.info(
        json.dumps(
            {
                "event": "odds_ingestion_summary",
                "target_date": target_date.isoformat(),
                "persisted_quotes": persisted_quotes,
                "matches_with_odds": matches_with_odds,
                "skipped_matches": skipped_matches,
                "failure_count": len(failures),
                "skip_counters": skip_counters,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    store_metric(
        connection_factory,
        metric_name="matches_with_odds",
        worker_name="odds_ingestion",
        pipeline_run_id=pipeline_run_id,
        target_date=target_date,
        metric_value=matches_with_odds,
    )
    store_metric(
        connection_factory,
        metric_name="odds_ingestion_skipped_by_reason",
        worker_name="odds_ingestion",
        pipeline_run_id=pipeline_run_id,
        target_date=target_date,
        json_value=json.dumps(skip_counters, ensure_ascii=True, sort_keys=True),
    )
    if failures:
        LOGGER.error("Matches with odds ingestion failures: %s", ", ".join(failures))
        raise RuntimeError("Odds ingestion failed for matches: " + ", ".join(failures))
    return persisted_quotes


def main() -> int:
    configure_logging()
    try:
        run_once()
    except (RuntimeError, ValueError, ESPNProviderError) as exc:
        _log_worker_error(
            source="odds_ingestion",
            league=None,
            match_id=None,
            context="main",
            error=exc,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
