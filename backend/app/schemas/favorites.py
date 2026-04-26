from __future__ import annotations

from pydantic import BaseModel, Field


class FavoriteRead(BaseModel):
    id: str
    saved_at: str
    liga: str
    match: str
    market: str
    prob: float = Field(ge=0.0, le=1.0)
    fair_odds: float = Field(gt=0.0)
    offered_odds: float = Field(gt=1.0)
    edge: float
    kelly_pct: float
    stake_units: float = Field(ge=0.0)


class FavoriteCreateRequest(BaseModel):
    liga: str
    match: str
    market: str
    prob: float = Field(ge=0.0, le=1.0)
    fair_odds: float = Field(gt=0.0)
    offered_odds: float = Field(gt=1.0)
    edge: float
    kelly_pct: float
    stake_units: float = Field(ge=0.0)


class FavoriteSummaryRead(BaseModel):
    count: int = Field(ge=0)
    total_stake_units: float = Field(ge=0.0)
    average_edge: float
    average_probability: float = Field(ge=0.0, le=1.0)


class FavoriteListResponse(BaseModel):
    items: list[FavoriteRead]
    summary: FavoriteSummaryRead
