from __future__ import annotations

import os

import pytest

from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import (
    PostgresConnectionError,
    PostgresSettings,
    create_postgres_connection_factory,
)


def _integration_settings() -> PostgresSettings | None:
    if not all(
        os.getenv(var, "").strip()
        for var in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    ):
        return None
    return PostgresSettings()


@pytest.fixture(scope="session")
def pg_connection_factory():
    settings = _integration_settings()
    if settings is None:
        pytest.skip("Integration tests require POSTGRES_HOST/DB/USER/PASSWORD env vars")
    try:
        factory = create_postgres_connection_factory(settings)
        ensure_postgres_schema(factory)
        return factory
    except PostgresConnectionError as exc:
        pytest.skip(f"Could not connect to PostgreSQL: {exc}")
