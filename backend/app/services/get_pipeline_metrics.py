from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import psycopg2

from backend.app.repositories.postgres.connection import PostgresConnectionError, PostgresConnectionFactory


PIPELINE_METRICS_QUERY = """
WITH ranked_metrics AS (
    SELECT
        metric_name,
        worker_name,
        pipeline_run_id,
        target_date,
        metric_value,
        json_value,
        recorded_at,
        ROW_NUMBER() OVER (
            PARTITION BY metric_name
            ORDER BY recorded_at DESC, id DESC
        ) AS row_number
    FROM pipeline_metrics
    WHERE metric_name IN (
        'matches_ingested',
        'matches_with_odds',
        'matches_analyzed',
        'picks_generated',
        'picks_settled'
    )
    OR metric_name LIKE '%_skipped_by_reason'
)
SELECT
    metric_name,
    worker_name,
    pipeline_run_id,
    target_date,
    metric_value,
    json_value,
    recorded_at
FROM ranked_metrics
WHERE row_number = 1
"""


@dataclass(frozen=True)
class PipelineMetricValue:
    value: int | dict[str, int]
    worker_name: str
    pipeline_run_id: str
    target_date: date | None
    updated_at: datetime


@dataclass(frozen=True)
class PipelineMetricsSnapshot:
    status: str
    metrics: dict[str, PipelineMetricValue]
    detail: str | None = None


class GetPipelineMetricsService:
    def __init__(self, connection_factory: PostgresConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def get(self) -> PipelineMetricsSnapshot:
        try:
            with self._connection_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(PIPELINE_METRICS_QUERY)
                    rows = cursor.fetchall()
        except (PostgresConnectionError, psycopg2.Error) as exc:
            return PipelineMetricsSnapshot(status="degraded", metrics={}, detail=str(exc))

        metrics: dict[str, PipelineMetricValue] = {}
        skipped_by_reason: dict[str, int] = {}
        skipped_source_worker = "aggregated"
        skipped_target_date: date | None = None
        skipped_updated_at: datetime | None = None

        skipped_pipeline_run_id = "aggregated"

        for metric_name, worker_name, pipeline_run_id, target_date, metric_value, json_value, updated_at in rows:
            if str(metric_name).endswith("_skipped_by_reason"):
                payload = json_value if isinstance(json_value, dict) else {}
                for key, value in payload.items():
                    skipped_by_reason[str(key)] = skipped_by_reason.get(str(key), 0) + int(value)
                if skipped_updated_at is None or updated_at > skipped_updated_at:
                    skipped_updated_at = updated_at
                    skipped_target_date = target_date
                    skipped_pipeline_run_id = str(pipeline_run_id)
                continue

            metrics[str(metric_name)] = PipelineMetricValue(
                value=int(metric_value or 0),
                worker_name=str(worker_name),
                pipeline_run_id=str(pipeline_run_id),
                target_date=target_date,
                updated_at=updated_at,
            )

        if skipped_updated_at is not None:
            metrics["skipped_by_reason"] = PipelineMetricValue(
                value=skipped_by_reason,
                worker_name=skipped_source_worker,
                pipeline_run_id=skipped_pipeline_run_id,
                target_date=skipped_target_date,
                updated_at=skipped_updated_at,
            )

        return PipelineMetricsSnapshot(status="ok", metrics=metrics)
