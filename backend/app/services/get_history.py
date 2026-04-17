from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.app.domain.models import Pick, Result
from backend.app.repositories.contracts import PickRepository, ResultRepository


@dataclass(frozen=True)
class HistoryItem:
    pick: Pick
    result: Result


class GetHistoryService:
    def __init__(self, picks: PickRepository, results: ResultRepository) -> None:
        self._picks = picks
        self._results = results

    def list_for_date(self, target_date: date) -> list[HistoryItem]:
        items: list[HistoryItem] = []
        for result in self._results.list_results_for_day(target_date):
            pick = self._picks.get_pick(result.pick_id)
            if pick is None:
                continue
            items.append(HistoryItem(pick=pick, result=result))
        return items
