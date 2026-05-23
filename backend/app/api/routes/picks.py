from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from backend.app.api.dependencies import get_daily_picks_service
from backend.app.api.rate_limiter import limiter
from backend.app.core.time import utc_today
from backend.app.schemas.picks import PickRead
from backend.app.services.get_daily_picks import GetDailyPicksService


router = APIRouter()


@router.get("", response_model=list[PickRead])
@limiter.limit("60/minute")
def get_picks(
    request: Request,
    service: Annotated[GetDailyPicksService, Depends(get_daily_picks_service)],
    day: date = Query(default_factory=utc_today),
    limit: int = Query(default=10, ge=1, le=100),
) -> list[PickRead]:
    picks = service.get_for_date(target_date=day, limit=limit)
    return [PickRead.from_domain(item) for item in picks]
