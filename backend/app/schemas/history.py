from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.services.get_history import HistoryItem


class HistoryItemRead(BaseModel):
    pick_id: str
    match_id: str
    market: str
    selection: str
    probability: float = Field(ge=0.0, le=1.0)
    offered_odds: float = Field(gt=1.0)
    closing_odds: float | None = Field(default=None, gt=1.0)
    clv_absolute: float | None = None
    clv_percent: float | None = None
    stake_fraction: float = Field(ge=0.0)
    stake_units: float = Field(ge=0.0)
    profit_units: float
    roi: float | None = None
    provider: str | None = None
    status: str
    settled_at: datetime | None = None

    @classmethod
    def from_domain(cls, item: HistoryItem) -> "HistoryItemRead":
        roi = None if item.result.stake_units == 0 else item.result.profit_units / item.result.stake_units
        return cls(
            pick_id=item.pick.id,
            match_id=item.pick.match_id,
            market=item.pick.market,
            selection=item.pick.selection,
            probability=item.pick.probability,
            offered_odds=item.pick.offered_odds,
            closing_odds=item.pick.closing_odds,
            clv_absolute=item.pick.clv_absolute,
            clv_percent=item.pick.clv_percent,
            stake_fraction=item.pick.stake_fraction,
            stake_units=item.result.stake_units,
            profit_units=item.result.profit_units,
            roi=roi,
            provider=item.pick.provider,
            status=item.result.status,
            settled_at=item.result.settled_at,
        )


class HistoryResponse(BaseModel):
    items: list[HistoryItemRead]
    total_profit_units: float
    total_stake_units: float
    roi: float | None = None
