from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.api.dependencies import get_match_detail_service
from backend.app.api.rate_limiter import limiter
from backend.app.schemas.matches import MatchDetailRead, MatchRead, OddsQuoteRead
from backend.app.schemas.picks import PickRead
from backend.app.services.get_match_detail import GetMatchDetailService


router = APIRouter()


@router.get("/{match_id}", response_model=MatchDetailRead)
@limiter.limit("60/minute")
def get_match(
    request: Request,
    match_id: str,
    service: Annotated[GetMatchDetailService, Depends(get_match_detail_service)],
) -> MatchDetailRead:
    match, odds, picks = service.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return MatchDetailRead(
        match=MatchRead.from_domain(match),
        odds=[OddsQuoteRead.from_domain(item) for item in odds],
        picks=[PickRead.from_domain(item) for item in picks],
    )
