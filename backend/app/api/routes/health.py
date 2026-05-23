from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from backend.app.api.dependencies import get_health_service
from backend.app.schemas.health import HealthCheckRead, HealthMetricsRead, HealthResponse
from backend.app.services.get_health import GetHealthService


router = APIRouter()


@router.get("", response_model=HealthResponse)
def get_health(
    request: Request,
    response: Response,
    service: Annotated[GetHealthService, Depends(get_health_service)],
) -> HealthResponse:
    snapshot = service.get()
    checks = {
        name: HealthCheckRead(status=check.status, ok=check.ok, detail=check.detail)
        for name, check in snapshot.checks.items()
    }

    scheduler_thread = getattr(request.app.state, "embedded_scheduler_thread", None)
    if scheduler_thread is not None:
        alive = scheduler_thread.is_alive()
        checks["scheduler"] = HealthCheckRead(
            status="ok" if alive else "error",
            ok=alive,
            detail="running" if alive else "dead",
        )

    db_ok = snapshot.checks["database"].ok
    scheduler_ok = checks.get("scheduler", HealthCheckRead(status="ok", ok=True)).ok
    if not db_ok or not scheduler_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    overall_status = snapshot.status if db_ok and scheduler_ok else "error"
    return HealthResponse(
        status=overall_status,
        checks=checks,
        last_ingestion_at=snapshot.last_ingestion_at,
        last_analysis_at=snapshot.last_analysis_at,
        metrics=HealthMetricsRead(
            database_latency_ms=snapshot.metrics.database_latency_ms,
            matches_total=snapshot.metrics.matches_total,
            odds_total=snapshot.metrics.odds_total,
            analyses_total=snapshot.metrics.analyses_total,
        ),
    )
