from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from backend.app.domain.models import Result
from backend.app.repositories.contracts import ResultRepository
from backend.app.repositories.postgres.base import PostgresRepository


class PostgresResultRepository(PostgresRepository, ResultRepository):
    def list_results_for_day(self, target_date: date) -> list[Result]:
        query = """
        SELECT id, pick_id, status, stake_units, profit_units, settled_selection, settled_at, created_at
        FROM results
        WHERE (settled_at AT TIME ZONE 'UTC')::date = %s
        ORDER BY settled_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (target_date,))
                rows = cursor.fetchall()
        return [self._row_to_result(row) for row in rows]

    def list_results_for_pick(self, pick_id: str) -> list[Result]:
        query = """
        SELECT id, pick_id, status, stake_units, profit_units, settled_selection, settled_at, created_at
        FROM results
        WHERE pick_id = %s
        ORDER BY settled_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (pick_id,))
                rows = cursor.fetchall()
        return [self._row_to_result(row) for row in rows]

    def settle_pick(self, pick_id: str, stake_units: float, profit_units: float, status: str) -> Result:
        settled_at = datetime.now(timezone.utc)
        query = """
        INSERT INTO results (id, pick_id, status, stake_units, profit_units, settled_selection, settled_at)
        VALUES (%s, %s, %s, %s, %s, NULL, %s)
        ON CONFLICT (pick_id) DO UPDATE SET
            status = EXCLUDED.status,
            stake_units = EXCLUDED.stake_units,
            profit_units = EXCLUDED.profit_units,
            settled_at = EXCLUDED.settled_at
        RETURNING id, pick_id, status, stake_units, profit_units, settled_selection, settled_at, created_at
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (str(uuid4()), pick_id, status, stake_units, profit_units, settled_at))
                row = cursor.fetchone()
            conn.commit()
        return self._row_to_result(row)

    @staticmethod
    def _row_to_result(row: tuple) -> Result:
        return Result(
            id=row[0],
            pick_id=row[1],
            status=row[2],
            stake_units=float(row[3]),
            profit_units=float(row[4]),
            settled_selection=row[5],
            settled_at=row[6],
            created_at=row[7],
        )
