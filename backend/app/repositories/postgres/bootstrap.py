from __future__ import annotations

from pathlib import Path

from backend.app.core.logging import get_logger


LOGGER = get_logger(__name__)
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DOMAIN_SCHEMAS_PATH = Path(__file__).resolve().parent / "domain_schemas.sql"


def ensure_postgres_schema(connection_factory) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    domain_schemas_sql = DOMAIN_SCHEMAS_PATH.read_text(encoding="utf-8")
    with connection_factory() as conn:
        with conn.cursor() as cursor:
            cursor.execute(schema_sql)
            cursor.execute(domain_schemas_sql)
        conn.commit()
    LOGGER.info("Ensured PostgreSQL schema from %s and %s", SCHEMA_PATH, DOMAIN_SCHEMAS_PATH)
