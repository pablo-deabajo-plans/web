from __future__ import annotations

from pathlib import Path

from backend.app.core.logging import get_logger


LOGGER = get_logger(__name__)
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def ensure_postgres_schema(connection_factory) -> None:
    statements = [chunk.strip() for chunk in SCHEMA_PATH.read_text(encoding="utf-8").split(";") if chunk.strip()]
    with connection_factory() as conn:
        with conn.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
        conn.commit()
    LOGGER.info("Ensured PostgreSQL schema from %s", SCHEMA_PATH)
