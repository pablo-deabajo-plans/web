from __future__ import annotations

import json

from backend.app.repositories.contracts import AuditLogRepository
from backend.app.repositories.postgres.base import PostgresRepository


class PostgresAuditLogRepository(PostgresRepository, AuditLogRepository):
    def log(self, user_id: str | None, action: str, metadata: dict) -> None:
        query = """
        INSERT INTO audit_log (user_id, action, metadata)
        VALUES (%s, %s, %s)
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (user_id, action, json.dumps(metadata)))
