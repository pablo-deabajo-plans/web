from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthCheckRead(BaseModel):
    status: str
    ok: bool
    detail: str | None = None


class HealthMetricsRead(BaseModel):
    database_latency_ms: float
    matches_total: int
    odds_total: int
    analyses_total: int


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, HealthCheckRead]
    last_ingestion_at: datetime | None = None
    last_analysis_at: datetime | None = None
    metrics: HealthMetricsRead
