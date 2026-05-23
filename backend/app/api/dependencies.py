from __future__ import annotations

import os
import secrets
from functools import lru_cache

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core import TTLCache, settings
from backend.app.repositories.in_memory import (
    InMemoryAuditLogRepository,
    InMemoryLoginAttemptRepository,
    InMemoryMatchRepository,
    InMemoryOddsRepository,
    InMemoryPickRepository,
    InMemoryResultRepository,
    InMemoryUserRepository,
)
from backend.app.repositories.file_favorites import FileFavoriteRepository
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.repositories.postgres.audit_log import PostgresAuditLogRepository
from backend.app.repositories.postgres.login_attempts import PostgresLoginAttemptRepository
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.repositories.postgres.odds import PostgresOddsRepository
from backend.app.repositories.postgres.picks import PostgresPickRepository
from backend.app.repositories.postgres.results import PostgresResultRepository
from backend.app.repositories.postgres.users import PostgresUserRepository
from backend.app.services.auth import AuthService
from backend.app.services.get_daily_picks import GetDailyPicksService
from backend.app.services.dashboard import DashboardService
from backend.app.services.favorites import FavoritesService
from backend.app.services.get_health import GetHealthService
from backend.app.services.get_history import GetHistoryService
from backend.app.services.get_match_detail import GetMatchDetailService
from backend.app.services.get_matches import GetMatchesService
from backend.app.services.get_pipeline_metrics import GetPipelineMetricsService
from backend.app.services.roi_service import ROIService


_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


def _postgres_configured() -> bool:
    return all(
        [
            settings_postgres
            for settings_postgres in (
                os.getenv("POSTGRES_HOST", "").strip(),
                os.getenv("POSTGRES_DB", "").strip(),
                os.getenv("POSTGRES_USER", "").strip(),
                os.getenv("POSTGRES_PASSWORD", "").strip(),
            )
        ]
    )


@lru_cache(maxsize=1)
def _read_cache() -> TTLCache:
    return TTLCache()


@lru_cache(maxsize=1)
def _connection_factory():
    return create_postgres_connection_factory()


@lru_cache(maxsize=1)
def _match_repository():
    if _postgres_configured():
        return PostgresMatchRepository(_connection_factory())
    return InMemoryMatchRepository()


@lru_cache(maxsize=1)
def _odds_repository():
    if _postgres_configured():
        return PostgresOddsRepository(_connection_factory())
    return InMemoryOddsRepository()


@lru_cache(maxsize=1)
def _pick_repository():
    if _postgres_configured():
        return PostgresPickRepository(_connection_factory())
    return InMemoryPickRepository()


@lru_cache(maxsize=1)
def _result_repository():
    if _postgres_configured():
        return PostgresResultRepository(_connection_factory())
    return InMemoryResultRepository()


@lru_cache(maxsize=1)
def _user_repository():
    if _postgres_configured():
        return PostgresUserRepository(_connection_factory())
    return InMemoryUserRepository()


@lru_cache(maxsize=1)
def _login_attempt_repository():
    if _postgres_configured():
        return PostgresLoginAttemptRepository(_connection_factory())
    return InMemoryLoginAttemptRepository()


@lru_cache(maxsize=1)
def _audit_log_repository():
    if _postgres_configured():
        return PostgresAuditLogRepository(_connection_factory())
    return InMemoryAuditLogRepository()


@lru_cache(maxsize=1)
def _favorite_repository() -> FileFavoriteRepository:
    return FileFavoriteRepository()


def require_authenticated_request(
    api_key: str | None = Security(_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> None:
    configured_secret = settings.api_auth_key.strip()
    if not configured_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )

    provided_secret = api_key or (bearer.credentials if bearer is not None else None)
    if not provided_secret or not secrets.compare_digest(provided_secret, configured_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API credentials",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def get_matches_service() -> GetMatchesService:
    return GetMatchesService(_match_repository(), cache=_read_cache(), ttl_seconds=settings.cache_ttl_matches_seconds)


def get_match_detail_service() -> GetMatchDetailService:
    return GetMatchDetailService(
        _match_repository(),
        _odds_repository(),
        _pick_repository(),
        cache=_read_cache(),
        ttl_seconds=settings.cache_ttl_match_detail_seconds,
    )


def get_daily_picks_service() -> GetDailyPicksService:
    return GetDailyPicksService(_pick_repository(), cache=_read_cache(), ttl_seconds=settings.cache_ttl_daily_picks_seconds)


def get_health_service() -> GetHealthService:
    return GetHealthService(_connection_factory())


def get_pipeline_metrics_service() -> GetPipelineMetricsService:
    return GetPipelineMetricsService(_connection_factory())


def get_roi_service() -> ROIService:
    return ROIService(
        _connection_factory(),
        cache=_read_cache(),
        ttl_seconds=settings.cache_ttl_history_seconds,
    )


def get_history_service() -> GetHistoryService:
    return GetHistoryService(
        _pick_repository(),
        _result_repository(),
        cache=_read_cache(),
        ttl_seconds=settings.cache_ttl_history_seconds,
    )


def get_dashboard_service() -> DashboardService:
    return _dashboard_service()


@lru_cache(maxsize=1)
def _dashboard_service() -> DashboardService:
    return DashboardService(_odds_repository())


def get_match_repository():
    return _match_repository()


def get_pick_repository():
    return _pick_repository()


def get_favorites_service() -> FavoritesService:
    return FavoritesService(_favorite_repository())


def get_user_repository():
    return _user_repository()


def get_auth_service() -> AuthService:
    return AuthService(
        _user_repository(),
        settings.session_secret_key,
        settings.session_ttl_seconds,
        _login_attempt_repository(),
    )


def get_audit_log_repository():
    return _audit_log_repository()
