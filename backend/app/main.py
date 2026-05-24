import asyncio
import contextlib
from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import Thread
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core import configure_logging, settings
from backend.app.core.logging import get_logger
from backend.app.api.dependencies import require_authenticated_request
from backend.app.api.rate_limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.jobs import router as jobs_router
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
from backend.app.web import router as web_router
from backend.workers import scheduler as embedded_scheduler


LOGGER = get_logger(__name__)


def _embedded_scheduler_enabled() -> bool:
    return os.getenv("EMBEDDED_SCHEDULER_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _start_embedded_scheduler(app: FastAPI) -> None:
    if not _embedded_scheduler_enabled():
        return
    worker_thread = getattr(app.state, "embedded_scheduler_thread", None)
    if worker_thread and worker_thread.is_alive():
        return
    embedded_scheduler.STOP_REQUESTED.clear()
    worker_thread = Thread(
        target=embedded_scheduler.run_forever,
        name="embedded-render-scheduler",
        daemon=True,
    )
    worker_thread.start()
    app.state.embedded_scheduler_thread = worker_thread
    LOGGER.info("Embedded scheduler started inside FastAPI process")


async def _scheduler_watchdog(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(60)
        thread = getattr(app.state, "embedded_scheduler_thread", None)
        if thread is not None and not thread.is_alive():
            LOGGER.warning("Embedded scheduler thread died — restarting")
            _start_embedded_scheduler(app)


def _postgres_env_configured() -> bool:
    if os.getenv("DATABASE_URL", "").strip():
        return True
    return all(
        os.getenv(v, "").strip()
        for v in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if _postgres_env_configured():
        try:
            ensure_postgres_schema(create_postgres_connection_factory())
        except Exception as exc:
            LOGGER.warning("PostgreSQL schema bootstrap failed — continuing: %s", exc)
    _start_embedded_scheduler(app)
    watchdog_task = asyncio.create_task(_scheduler_watchdog(app)) if _embedded_scheduler_enabled() else None
    yield
    if watchdog_task is not None:
        watchdog_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watchdog_task
    if _embedded_scheduler_enabled():
        embedded_scheduler.STOP_REQUESTED.set()
        LOGGER.info("Embedded scheduler stop requested")


async def _request_tracing(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "frame-src 'none'; "
        "object-src 'none'; "
        "base-uri 'self';"
    )
    return response


def create_app() -> FastAPI:
    configure_logging()
    settings.validate_security()
    app = FastAPI(title="Gordon BetScanner Backend", version="0.1.0", lifespan=_lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(BaseHTTPMiddleware, dispatch=_security_headers)
    app.add_middleware(BaseHTTPMiddleware, dispatch=_request_tracing)
    static_dir = Path(__file__).resolve().parent / "web" / "static"
    app.mount("/assets", StaticFiles(directory=str(static_dir)), name="assets")
    app.include_router(web_router)
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
    app.include_router(jobs_router, prefix="/jobs", tags=["jobs"], dependencies=protected_dependencies)
    app.title = settings.app_name
    return app


app = create_app()

_error_templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "web" / "templates")
)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    return _error_templates.TemplateResponse(
        request, "errors/404.html", {}, status_code=404
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    LOGGER.exception("Unhandled exception: %s", exc)
    return _error_templates.TemplateResponse(
        request, "errors/500.html", {}, status_code=500
    )
