from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date

from backend.app.domain.models import Match
from backend.app.repositories.contracts import MatchRepository


def run_match_ingestion(
    *,
    target_date: date,
    fetch_matches: Callable[[date], Sequence[Match]],
    repository: MatchRepository,
) -> int:
    matches = list(fetch_matches(target_date))
    repository.upsert_matches(matches)
    return len(matches)
