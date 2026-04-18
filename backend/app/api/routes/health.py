from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from backend.app.api.dependencies import get_health_service
from backend.app.schemas.health import HealthCheckRead, HealthMetricsRead, HealthResponse
from backend.app.services.get_health import GetHealthService


router = APIRouter()


@router.get("", response_model=HealthResponse)
def get_health(
    response: Response,
    service: Annotated[GetHealthService, Depends(get_health_service)],
) -> HealthResponse:
    snapshot = service.get()
    if not snapshot.checks["database"].ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status=snapshot.status,
        checks={
            name: HealthCheckRead(status=check.status, ok=check.ok, detail=check.detail)
            for name, check in snapshot.checks.items()
        },
        last_ingestion_at=snapshot.last_ingestion_at,
        last_analysis_at=snapshot.last_analysis_at,
        metrics=HealthMetricsRead(
            database_latency_ms=snapshot.metrics.database_latency_ms,
            matches_total=snapshot.metrics.matches_total,
            odds_total=snapshot.metrics.odds_total,
            analyses_total=snapshot.metrics.analyses_total,
        ),
    )
