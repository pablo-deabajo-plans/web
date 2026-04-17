from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.dependencies import get_history_service
from backend.app.schemas.history import HistoryItemRead, HistoryResponse
from backend.app.services.get_history import GetHistoryService


router = APIRouter()


@router.get("", response_model=HistoryResponse)
def get_history(
    service: Annotated[GetHistoryService, Depends(get_history_service)],
    day: date = Query(default_factory=lambda: datetime.now(timezone.utc).date()),
) -> HistoryResponse:
    items = service.list_for_date(day)
    total_profit = sum(item.result.profit_units for item in items)
    total_stake = sum(item.result.stake_units for item in items)
    roi = None if total_stake == 0 else total_profit / total_stake
    return HistoryResponse(
        items=[HistoryItemRead.from_domain(item) for item in items],
        total_profit_units=total_profit,
        total_stake_units=total_stake,
        roi=roi,
    )
