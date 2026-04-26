from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from backend.app.api.dependencies import get_pipeline_metrics_service
from backend.app.schemas.metrics import PipelineMetricRead, PipelineMetricsResponse
from backend.app.services.get_pipeline_metrics import GetPipelineMetricsService


router = APIRouter()


@router.get("", response_model=PipelineMetricsResponse)
def get_metrics(
    response: Response,
    service: Annotated[GetPipelineMetricsService, Depends(get_pipeline_metrics_service)],
) -> PipelineMetricsResponse:
    snapshot = service.get()
    if snapshot.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return PipelineMetricsResponse(
        status=snapshot.status,
        detail=snapshot.detail,
        metrics={
            name: PipelineMetricRead(
                worker_name=item.worker_name,
                target_date=item.target_date,
                updated_at=item.updated_at,
                value=item.value,
            )
            for name, item in snapshot.metrics.items()
        },
    )
