from __future__ import annotations

from datetime import date, datetime
from typing import Union

from pydantic import BaseModel


class PipelineMetricRead(BaseModel):
    worker_name: str
    target_date: date | None = None
    updated_at: datetime
    value: int | dict[str, int]


class PipelineMetricsResponse(BaseModel):
    status: str
    detail: str | None = None
    metrics: dict[str, PipelineMetricRead]
