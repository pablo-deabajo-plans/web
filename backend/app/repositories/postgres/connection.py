from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PGConnection

from backend.app.core.logging import get_logger


LOGGER = get_logger(__name__)


class PostgresConnectionError(RuntimeError):
    """Raised when a PostgreSQL connection cannot be created."""


@dataclass(frozen=True)
class PostgresSettings:
    host: str = os.getenv("POSTGRES_HOST", "")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "")
    user: str = os.getenv("POSTGRES_USER", "")
    password: str = os.getenv("POSTGRES_PASSWORD", "")
    sslmode: str = os.getenv("POSTGRES_SSLMODE", "prefer")
    connect_timeout: int = int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "10"))
    application_name: str = os.getenv("POSTGRES_APPLICATION_NAME", "gordon-betscanner-backend")

    def validate(self) -> None:
        missing = []
        if not self.host:
            missing.append("POSTGRES_HOST")
        if not self.database:
            missing.append("POSTGRES_DB")
        if not self.user:
            missing.append("POSTGRES_USER")
        if not self.password:
            missing.append("POSTGRES_PASSWORD")
        if missing:
            raise PostgresConnectionError(
                "Missing required PostgreSQL environment variables: " + ", ".join(missing)
            )


class PostgresConnectionFactory:
    def __init__(self, settings: PostgresSettings | None = None) -> None:
        self._settings = settings or PostgresSettings()

    def __call__(self) -> PGConnection:
        return self.create_connection()

    def create_connection(self) -> PGConnection:
        self._settings.validate()
        try:
            return psycopg2.connect(
                host=self._settings.host,
                port=self._settings.port,
                dbname=self._settings.database,
                user=self._settings.user,
                password=self._settings.password,
                sslmode=self._settings.sslmode,
                connect_timeout=self._settings.connect_timeout,
                application_name=self._settings.application_name,
            )
        except psycopg2.Error as exc:
            LOGGER.exception(
                "Failed to connect to PostgreSQL host=%s port=%s db=%s user=%s",
                self._settings.host,
                self._settings.port,
                self._settings.database,
                self._settings.user,
            )
            raise PostgresConnectionError("Could not establish PostgreSQL connection") from exc

    @contextmanager
    def connection(self) -> Iterator[PGConnection]:
        conn = self.create_connection()
        try:
            yield conn
        finally:
            conn.close()


def create_postgres_connection_factory(
    settings: PostgresSettings | None = None,
) -> PostgresConnectionFactory:
    return PostgresConnectionFactory(settings=settings)
