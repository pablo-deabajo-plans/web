from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.domain.models import Pick


class PickRead(BaseModel):
    id: str
    match_id: str
    market: str
    selection: str
    probability: float = Field(ge=0.0, le=1.0)
    fair_odds: float = Field(ge=0.0)
    offered_odds: float = Field(gt=1.0)
    closing_odds: float | None = Field(default=None, gt=1.0)
    clv_absolute: float | None = None
    clv_percent: float | None = None
    edge: float
    stake_fraction: float = Field(ge=0.0)
    provider: str | None = None
    created_at: datetime | None = None

    @classmethod
    def from_domain(cls, pick: Pick) -> "PickRead":
        return cls(
            id=pick.id,
            match_id=pick.match_id,
            market=pick.market,
            selection=pick.selection,
            probability=pick.probability,
            fair_odds=pick.fair_odds,
            offered_odds=pick.offered_odds,
            closing_odds=pick.closing_odds,
            clv_absolute=pick.clv_absolute,
            clv_percent=pick.clv_percent,
            edge=pick.edge,
            stake_fraction=pick.stake_fraction,
            provider=pick.provider,
            created_at=pick.created_at,
        )
