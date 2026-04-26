from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from backend.app.core import configure_logging, settings
from backend.app.api.dependencies import require_authenticated_request
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.history import router as history_router
from backend.app.api.routes.dashboard import router as dashboard_router
from backend.app.api.routes.favorites import router as favorites_router
from backend.app.api.routes.match import router as match_router
from backend.app.api.routes.matches import router as matches_router
from backend.app.api.routes.metrics import router as metrics_router
from backend.app.api.routes.performance import router as performance_router
from backend.app.api.routes.picks import router as picks_router
from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import create_postgres_connection_factory


@asynccontextmanager
async def _lifespan(_: FastAPI):
    ensure_postgres_schema(create_postgres_connection_factory())
    yield


def create_app() -> FastAPI:
    configure_logging()
    settings.validate_security()
    app = FastAPI(title="Gordon BetScanner Backend", version="0.1.0", lifespan=_lifespan)
    app.include_router(health_router, prefix="/health", tags=["health"])
    protected_dependencies = [Depends(require_authenticated_request)]
    app.include_router(metrics_router, prefix="/metrics", tags=["metrics"], dependencies=protected_dependencies)
    app.include_router(performance_router, prefix="/performance", tags=["performance"], dependencies=protected_dependencies)
    app.include_router(picks_router, prefix="/picks", tags=["picks"], dependencies=protected_dependencies)
    app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"], dependencies=protected_dependencies)
    app.include_router(favorites_router, prefix="/favorites", tags=["favorites"], dependencies=protected_dependencies)
    app.include_router(matches_router, prefix="/matches", tags=["matches"], dependencies=protected_dependencies)
    app.include_router(match_router, prefix="/match", tags=["match"], dependencies=protected_dependencies)
    app.include_router(history_router, prefix="/history", tags=["history"], dependencies=protected_dependencies)
    app.title = settings.app_name
    return app


app = create_app()
