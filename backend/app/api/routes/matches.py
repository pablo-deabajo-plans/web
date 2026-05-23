from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from backend.app.api.dependencies import get_matches_service
from backend.app.api.rate_limiter import limiter
from backend.app.core.time import utc_today
from backend.app.schemas.matches import MatchRead
from backend.app.services.get_matches import GetMatchesService


router = APIRouter()


@router.get("", response_model=list[MatchRead])
@limiter.limit("60/minute")
def get_matches(
    request: Request,
    service: Annotated[GetMatchesService, Depends(get_matches_service)],
    day: date = Query(default_factory=utc_today),
) -> list[MatchRead]:
    return [MatchRead.from_domain(match) for match in service.list_for_date(day)]
