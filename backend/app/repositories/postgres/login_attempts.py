from __future__ import annotations

import json
import time

import psycopg2

from backend.app.core.logging import get_logger
from backend.app.repositories.postgres.base import PostgresRepository


LOGGER = get_logger(__name__)

_GET = "SELECT timestamps FROM login_attempts WHERE key = %s"
_UPSERT = """
INSERT INTO login_attempts (key, timestamps, updated_at)
VALUES (%s, %s::jsonb, NOW())
ON CONFLICT (key) DO UPDATE SET
    timestamps = EXCLUDED.timestamps,
    updated_at = NOW()
"""
_DELETE = "DELETE FROM login_attempts WHERE key = %s"


class PostgresLoginAttemptRepository(PostgresRepository):
    def get_recent_failures(self, key: str, window_seconds: int) -> int:
        cutoff = time.time() - window_seconds
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(_GET, (key,))
                    row = cursor.fetchone()
        except psycopg2.Error:
            LOGGER.warning("login_attempts: read failed for key=%s, failing open", key)
            return 0
        if row is None:
            return 0
        return sum(1 for ts in (row[0] or []) if isinstance(ts, (int, float)) and ts >= cutoff)

    def record_failure(self, key: str) -> None:
        now = time.time()
        cutoff = now - 900
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(_GET, (key,))
                    row = cursor.fetchone()
                    kept = [ts for ts in (row[0] or []) if isinstance(ts, (int, float)) and ts >= cutoff] if row else []
                    kept.append(now)
                    cursor.execute(_UPSERT, (key, json.dumps(kept)))
        except psycopg2.Error:
            LOGGER.warning("login_attempts: write failed for key=%s", key)

    def clear_failures(self, key: str) -> None:
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(_DELETE, (key,))
        except psycopg2.Error:
            LOGGER.warning("login_attempts: clear failed for key=%s", key)
