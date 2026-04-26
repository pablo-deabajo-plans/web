from __future__ import annotations

from datetime import date
from uuid import uuid4


INSERT_PIPELINE_METRIC_QUERY = """
INSERT INTO pipeline_metrics (
    metric_name,
    worker_name,
    pipeline_run_id,
    target_date,
    metric_value,
    json_value,
    recorded_at,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
"""


def store_metric(
    connection_factory,
    *,
    metric_name: str,
    worker_name: str,
    pipeline_run_id: str | None,
    target_date: date | None,
    metric_value: int | None = None,
    json_value: str | None = None,
) -> None:
    resolved_pipeline_run_id = pipeline_run_id or str(uuid4())
    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                INSERT_PIPELINE_METRIC_QUERY,
                (
                    metric_name,
                    worker_name,
                    resolved_pipeline_run_id,
                    target_date,
                    metric_value,
                    json_value,
                ),
            )
        conn.commit()
