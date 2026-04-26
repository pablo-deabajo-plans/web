from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.domain.models import Result


class ResultRead(BaseModel):
    id: str
    pick_id: str
    status: str
    stake_units: float = Field(ge=0.0)
    profit_units: float
    settled_selection: str | None = None
    settled_at: datetime | None = None
    created_at: datetime | None = None

    @classmethod
    def from_domain(cls, result: Result) -> "ResultRead":
        return cls(
            id=result.id,
            pick_id=result.pick_id,
            status=result.status,
            stake_units=result.stake_units,
            profit_units=result.profit_units,
            settled_selection=result.settled_selection,
            settled_at=result.settled_at,
            created_at=result.created_at,
        )
