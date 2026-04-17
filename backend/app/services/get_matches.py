from __future__ import annotations

from datetime import date

from backend.app.domain.models import Match
from backend.app.repositories.contracts import MatchRepository


class GetMatchesService:
    def __init__(self, repository: MatchRepository) -> None:
        self._repository = repository

    def list_for_date(self, target_date: date) -> list[Match]:
        return list(self._repository.list_matches_for_day(target_date))
