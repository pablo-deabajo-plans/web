from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.services.roi_service import ROIGroupResult, ROIResult


class PerformanceMetricsRead(BaseModel):
    total_bets: int = Field(ge=0)
    total_stake: float = Field(ge=0.0)
    total_profit: float
    roi: float | None = None
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    pushes: int = Field(ge=0)

    @classmethod
    def from_domain(cls, result: ROIResult) -> "PerformanceMetricsRead":
        return cls(
            total_bets=result.total_bets,
            total_stake=result.total_stake,
            total_profit=result.total_profit,
            roi=result.roi,
            wins=result.wins,
            losses=result.losses,
            pushes=result.pushes,
        )


class PerformanceSummaryResponse(BaseModel):
    summary: PerformanceMetricsRead


class PerformanceBreakdownItemRead(BaseModel):
    key: str
    metrics: PerformanceMetricsRead

    @classmethod
    def from_domain(cls, result: ROIGroupResult) -> "PerformanceBreakdownItemRead":
        return cls(key=result.key, metrics=PerformanceMetricsRead.from_domain(result.metrics))


class PerformanceBreakdownResponse(BaseModel):
    items: list[PerformanceBreakdownItemRead]
