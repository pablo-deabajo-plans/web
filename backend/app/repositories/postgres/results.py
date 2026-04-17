from __future__ import annotations

from datetime import date, datetime, timezone

from backend.app.domain.models import Result
from backend.app.repositories.contracts import ResultRepository
from backend.app.repositories.postgres.base import PostgresRepository


class PostgresResultRepository(PostgresRepository, ResultRepository):
    def list_results_for_day(self, target_date: date) -> list[Result]:
        query = """
        SELECT id, pick_id, status, stake_units, profit_units, settled_at
        FROM results
        WHERE DATE(settled_at) = %s
        ORDER BY settled_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (target_date,))
                rows = cursor.fetchall()
        return [Result(*row) for row in rows]

    def list_results_for_pick(self, pick_id: str) -> list[Result]:
        query = """
        SELECT id, pick_id, status, stake_units, profit_units, settled_at
        FROM results
        WHERE pick_id = %s
        ORDER BY settled_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (pick_id,))
                rows = cursor.fetchall()
        return [Result(*row) for row in rows]

    def settle_pick(self, pick_id: str, stake_units: float, profit_units: float, status: str) -> Result:
        settled_at = datetime.now(timezone.utc)
        query = """
        INSERT INTO results (id, pick_id, status, stake_units, profit_units, settled_at)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
        RETURNING id, pick_id, status, stake_units, profit_units, settled_at
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (pick_id, status, stake_units, profit_units, settled_at))
                row = cursor.fetchone()
            conn.commit()
        return Result(*row)
