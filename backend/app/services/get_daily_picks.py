from __future__ import annotations

from datetime import date

from backend.app.domain.models import DailyPicksQuery, Pick
from backend.app.domain.pricing import rank_picks
from backend.app.repositories.contracts import PickRepository


class GetDailyPicksService:
    def __init__(self, repository: PickRepository) -> None:
        self._repository = repository

    def execute(self, query: DailyPicksQuery) -> list[Pick]:
        picks = list(self._repository.list_picks_for_day(query.target_date))
        positive_edge = [pick for pick in picks if pick.edge > 0]
        return rank_picks(positive_edge, limit=query.limit)

    def get_for_date(self, target_date: date, limit: int = 10) -> list[Pick]:
        return self.execute(DailyPicksQuery(target_date=target_date, limit=limit))
