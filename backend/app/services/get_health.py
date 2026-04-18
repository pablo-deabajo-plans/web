from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

import psycopg2

from backend.app.repositories.postgres.connection import PostgresConnectionError, PostgresConnectionFactory


HEALTH_QUERY = """
WITH latest_ingestion AS (
    SELECT GREATEST(
        COALESCE((SELECT MAX(updated_at) FROM matches), '-infinity'::timestamptz),
        COALESCE((SELECT MAX(created_at) FROM odds), '-infinity'::timestamptz)
    ) AS value
),
latest_analysis AS (
    SELECT MAX(generated_at) AS value
    FROM analyses
),
table_counts AS (
    SELECT
        (SELECT COUNT(*) FROM matches) AS matches_total,
        (SELECT COUNT(*) FROM odds) AS odds_total,
        (SELECT COUNT(*) FROM analyses) AS analyses_total
)
SELECT
    NULLIF((SELECT value FROM latest_ingestion), '-infinity'::timestamptz) AS last_ingestion_at,
    (SELECT value FROM latest_analysis) AS last_analysis_at,
    matches_total,
    odds_total,
    analyses_total
FROM table_counts
"""


@dataclass(frozen=True)
class HealthCheck:
    status: str
    ok: bool
    detail: str | None = None


@dataclass(frozen=True)
class HealthMetrics:
    database_latency_ms: float
    matches_total: int
    odds_total: int
    analyses_total: int


@dataclass(frozen=True)
class HealthSnapshot:
    status: str
    checks: dict[str, HealthCheck]
    last_ingestion_at: datetime | None
    last_analysis_at: datetime | None
    metrics: HealthMetrics


class GetHealthService:
    def __init__(self, connection_factory: PostgresConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def get(self) -> HealthSnapshot:
        started = time.perf_counter()
        try:
            with self._connection_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(HEALTH_QUERY)
                    row = cursor.fetchone()
        except (PostgresConnectionError, psycopg2.Error) as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return HealthSnapshot(
                status="degraded",
                checks={"database": HealthCheck(status="error", ok=False, detail=str(exc))},
                last_ingestion_at=None,
                last_analysis_at=None,
                metrics=HealthMetrics(
                    database_latency_ms=latency_ms,
                    matches_total=0,
                    odds_total=0,
                    analyses_total=0,
                ),
            )

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        last_ingestion_at, last_analysis_at, matches_total, odds_total, analyses_total = row
        return HealthSnapshot(
            status="ok",
            checks={"database": HealthCheck(status="ok", ok=True)},
            last_ingestion_at=last_ingestion_at,
            last_analysis_at=last_analysis_at,
            metrics=HealthMetrics(
                database_latency_ms=latency_ms,
                matches_total=int(matches_total),
                odds_total=int(odds_total),
                analyses_total=int(analyses_total),
            ),
        )
