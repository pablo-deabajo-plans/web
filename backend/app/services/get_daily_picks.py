from __future__ import annotations

from datetime import date

from backend.app.core.cache import TTLCache
from backend.app.domain.models import DailyPicksQuery, Pick
from backend.app.domain.pricing import rank_picks
from backend.app.repositories.contracts import PickRepository


class GetDailyPicksService:
    def __init__(self, repository: PickRepository, cache: TTLCache | None = None, ttl_seconds: int = 0) -> None:
        self._repository = repository
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    def execute(self, query: DailyPicksQuery) -> list[Pick]:
        def _load() -> list[Pick]:
            picks = list(self._repository.list_picks_for_day(query.target_date))
            positive_edge = [pick for pick in picks if pick.edge > 0]
            return rank_picks(positive_edge, limit=query.limit)

        if self._cache is None or self._ttl_seconds <= 0:
            return _load()
        cache_key = f"{query.target_date.isoformat()}:{query.limit}"
        return self._cache.get_or_set("daily_picks", cache_key, self._ttl_seconds, _load)

    def get_for_date(self, target_date: date, limit: int = 10) -> list[Pick]:
        return self.execute(DailyPicksQuery(target_date=target_date, limit=limit))
