from __future__ import annotations

from backend.app.repositories import (
    InMemoryMatchRepository,
    InMemoryOddsRepository,
    InMemoryPickRepository,
    InMemoryResultRepository,
)
from backend.app.services.get_daily_picks import GetDailyPicksService
from backend.app.services.get_history import GetHistoryService
from backend.app.services.get_match_detail import GetMatchDetailService
from backend.app.services.get_matches import GetMatchesService


_match_repository = InMemoryMatchRepository()
_odds_repository = InMemoryOddsRepository()
_pick_repository = InMemoryPickRepository()
_result_repository = InMemoryResultRepository()


def get_matches_service() -> GetMatchesService:
    return GetMatchesService(_match_repository)


def get_match_detail_service() -> GetMatchDetailService:
    return GetMatchDetailService(_match_repository, _odds_repository, _pick_repository)


def get_daily_picks_service() -> GetDailyPicksService:
    return GetDailyPicksService(_pick_repository)


def get_history_service() -> GetHistoryService:
    return GetHistoryService(_pick_repository, _result_repository)
