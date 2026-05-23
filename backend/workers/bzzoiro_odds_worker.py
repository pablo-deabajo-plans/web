from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.domain.models import OddsQuote
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.repositories.postgres.odds import PostgresOddsRepository
from backend.app.repositories.providers.bzzoiro import (
    fetch_bzzoiro_events_for_date,
    fetch_bzzoiro_odds_comparison,
    find_bzzoiro_event,
    get_bzzoiro_token,
    parse_bzzoiro_comparison_odds,
)
from backend.workers.runtime import resolve_target_date


LOGGER = get_logger(__name__)


def _target_date_from_env() -> date:
    return resolve_target_date("ODDS_INGESTION_DATE")


def _snapshot_id(match_id: str, market: str, selection: str, sportsbook: str, captured_at: datetime) -> str:
    return str(uuid5(NAMESPACE_URL, f"bzzoiro:{match_id}:{market}:{selection}:{sportsbook}:{captured_at.isoformat()}"))


def run_once() -> int:
    token = get_bzzoiro_token()
    if not token:
        LOGGER.info("BZZOIRO_API_TOKEN not set, skipping bzzoiro odds ingestion")
        return 0

    target_date = _target_date_from_env()
    connection_factory = create_postgres_connection_factory()
    match_repo = PostgresMatchRepository(connection_factory)
    odds_repo = PostgresOddsRepository(connection_factory)

    matches = list(match_repo.list_matches_for_day(target_date))
    if not matches:
        LOGGER.info("bzzoiro_odds: no matches for target_date=%s", target_date.isoformat())
        return 0

    LOGGER.info("bzzoiro_odds: fetching events for date=%s", target_date.isoformat())
    bzzoiro_events = fetch_bzzoiro_events_for_date(target_date)
    LOGGER.info("bzzoiro_odds: found bzzoiro_events=%s", len(bzzoiro_events))

    persisted_quotes = 0
    matched_count = 0
    unmatched_count = 0

    for match in matches:
        bz_event = find_bzzoiro_event(match.home_team, match.away_team, bzzoiro_events)
        if bz_event is None:
            unmatched_count += 1
            LOGGER.debug(
                "bzzoiro_odds: no match found home=%s away=%s",
                match.home_team,
                match.away_team,
            )
            continue

        bz_event_id = bz_event.get("id")
        comparison = fetch_bzzoiro_odds_comparison(bz_event_id)
        if not comparison:
            continue

        snapshots = parse_bzzoiro_comparison_odds(comparison)
        if not snapshots:
            continue

        quotes = [
            OddsQuote(
                id=_snapshot_id(
                    match.id,
                    s["market"],
                    s["selection"],
                    s["sportsbook"],
                    s["captured_at"],
                ),
                match_id=match.id,
                market=s["market"],
                selection=s["selection"],
                decimal_odds=float(s["decimal_odds"]),
                sportsbook=s["sportsbook"],
                captured_at=s["captured_at"],
            )
            for s in snapshots
        ]

        odds_repo.upsert_odds(quotes)
        persisted_quotes += len(quotes)
        matched_count += 1

        LOGGER.info(
            "bzzoiro_odds: stored match_id=%s bz_event_id=%s competition=%s quotes=%s",
            match.id,
            bz_event_id,
            match.competition,
            len(quotes),
        )

    LOGGER.info(
        json.dumps(
            {
                "event": "bzzoiro_odds_summary",
                "target_date": target_date.isoformat(),
                "matches_total": len(matches),
                "matched_count": matched_count,
                "unmatched_count": unmatched_count,
                "persisted_quotes": persisted_quotes,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return persisted_quotes


def main() -> int:
    configure_logging()
    try:
        run_once()
    except Exception as exc:
        LOGGER.exception("bzzoiro_odds_worker failed error=%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
