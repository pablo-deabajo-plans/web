from __future__ import annotations

from datetime import date

from backend.app.core.cache import TTLCache
from backend.app.domain.models import Match
from backend.app.repositories.contracts import MatchRepository


class GetMatchesService:
    def __init__(self, repository: MatchRepository, cache: TTLCache | None = None, ttl_seconds: int = 0) -> None:
        self._repository = repository
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    def list_for_date(self, target_date: date) -> list[Match]:
        def _load() -> list[Match]:
            return list(self._repository.list_matches_for_day(target_date))

        if self._cache is None or self._ttl_seconds <= 0:
            return _load()
        return self._cache.get_or_set("matches", target_date.isoformat(), self._ttl_seconds, _load)
