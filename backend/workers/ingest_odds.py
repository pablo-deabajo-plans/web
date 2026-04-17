from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date

from backend.app.domain.models import OddsQuote
from backend.app.repositories.contracts import OddsRepository


def run_odds_ingestion(
    *,
    target_date: date,
    fetch_odds: Callable[[date], Sequence[OddsQuote]],
    repository: OddsRepository,
) -> int:
    quotes = list(fetch_odds(target_date))
    repository.upsert_odds(quotes)
    return len(quotes)
