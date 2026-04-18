from __future__ import annotations

from backend.app.core import TTLCache, settings
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.repositories.postgres.odds import PostgresOddsRepository
from backend.app.repositories.postgres.picks import PostgresPickRepository
from backend.app.repositories.postgres.results import PostgresResultRepository
from backend.app.services.get_daily_picks import GetDailyPicksService
from backend.app.services.get_health import GetHealthService
from backend.app.services.get_history import GetHistoryService
from backend.app.services.get_match_detail import GetMatchDetailService
from backend.app.services.get_matches import GetMatchesService
from backend.app.services.roi_service import ROIService


_connection_factory = create_postgres_connection_factory()
_match_repository = PostgresMatchRepository(_connection_factory)
_odds_repository = PostgresOddsRepository(_connection_factory)
_pick_repository = PostgresPickRepository(_connection_factory)
_result_repository = PostgresResultRepository(_connection_factory)
_read_cache = TTLCache()
_health_service = GetHealthService(_connection_factory)
_roi_service = ROIService(
    _match_repository,
    _pick_repository,
    _result_repository,
    cache=_read_cache,
    ttl_seconds=settings.cache_ttl_history_seconds,
)


def get_matches_service() -> GetMatchesService:
    return GetMatchesService(_match_repository, cache=_read_cache, ttl_seconds=settings.cache_ttl_matches_seconds)


def get_match_detail_service() -> GetMatchDetailService:
    return GetMatchDetailService(
        _match_repository,
        _odds_repository,
        _pick_repository,
        cache=_read_cache,
        ttl_seconds=settings.cache_ttl_match_detail_seconds,
    )


def get_daily_picks_service() -> GetDailyPicksService:
    return GetDailyPicksService(_pick_repository, cache=_read_cache, ttl_seconds=settings.cache_ttl_daily_picks_seconds)


def get_health_service() -> GetHealthService:
    return _health_service


def get_roi_service() -> ROIService:
    return _roi_service


def get_history_service() -> GetHistoryService:
    return GetHistoryService(_pick_repository, _result_repository, cache=_read_cache, ttl_seconds=settings.cache_ttl_history_seconds)
