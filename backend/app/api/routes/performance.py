from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.dependencies import get_roi_service
from backend.app.core.time import utc_today
from backend.app.schemas.performance import (
    PerformanceBreakdownItemRead,
    PerformanceBreakdownResponse,
    PerformanceSummaryResponse,
    PerformanceMetricsRead,
)
from backend.app.services.roi_service import ROIQuery, ROIService


router = APIRouter()


def _default_day() -> date:
    return utc_today()


@router.get("/summary", response_model=PerformanceSummaryResponse)
def get_performance_summary(
    service: Annotated[ROIService, Depends(get_roi_service)],
    start_date: date = Query(default_factory=_default_day),
    end_date: date = Query(default_factory=_default_day),
    league: str | None = Query(default=None),
    market: str | None = Query(default=None),
) -> PerformanceSummaryResponse:
    try:
        result = service.calculate(ROIQuery(start_date=start_date, end_date=end_date, league=league, market=market))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PerformanceSummaryResponse(summary=PerformanceMetricsRead.from_domain(result))


@router.get("/by-league", response_model=PerformanceBreakdownResponse)
def get_performance_by_league(
    service: Annotated[ROIService, Depends(get_roi_service)],
    start_date: date = Query(default_factory=_default_day),
    end_date: date = Query(default_factory=_default_day),
    market: str | None = Query(default=None),
) -> PerformanceBreakdownResponse:
    try:
        items = service.group_by_league(ROIQuery(start_date=start_date, end_date=end_date, market=market))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PerformanceBreakdownResponse(items=[PerformanceBreakdownItemRead.from_domain(item) for item in items])


@router.get("/by-market", response_model=PerformanceBreakdownResponse)
def get_performance_by_market(
    service: Annotated[ROIService, Depends(get_roi_service)],
    start_date: date = Query(default_factory=_default_day),
    end_date: date = Query(default_factory=_default_day),
    league: str | None = Query(default=None),
) -> PerformanceBreakdownResponse:
    try:
        items = service.group_by_market(ROIQuery(start_date=start_date, end_date=end_date, league=league))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PerformanceBreakdownResponse(items=[PerformanceBreakdownItemRead.from_domain(item) for item in items])
