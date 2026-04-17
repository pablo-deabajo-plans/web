from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.app.core.cache import TTLCache
from backend.app.domain.models import Pick, Result
from backend.app.repositories.contracts import PickRepository, ResultRepository


@dataclass(frozen=True)
class HistoryItem:
    pick: Pick
    result: Result


class GetHistoryService:
    def __init__(self, picks: PickRepository, results: ResultRepository, cache: TTLCache | None = None, ttl_seconds: int = 0) -> None:
        self._picks = picks
        self._results = results
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    def list_for_date(self, target_date: date) -> list[HistoryItem]:
        def _load() -> list[HistoryItem]:
            items: list[HistoryItem] = []
            for result in self._results.list_results_for_day(target_date):
                pick = self._picks.get_pick(result.pick_id)
                if pick is None:
                    continue
                items.append(HistoryItem(pick=pick, result=result))
            return items

        if self._cache is None or self._ttl_seconds <= 0:
            return _load()
        return self._cache.get_or_set("history", target_date.isoformat(), self._ttl_seconds, _load)
