from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PGConnection
from psycopg2.pool import ThreadedConnectionPool

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
    pool_minconn: int = int(os.getenv("POSTGRES_POOL_MINCONN", "1"))
    pool_maxconn: int = int(os.getenv("POSTGRES_POOL_MAXCONN", "10"))

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
        if self.pool_minconn <= 0:
            raise PostgresConnectionError("POSTGRES_POOL_MINCONN must be greater than zero")
        if self.pool_maxconn < self.pool_minconn:
            raise PostgresConnectionError("POSTGRES_POOL_MAXCONN must be greater than or equal to POSTGRES_POOL_MINCONN")


class PooledPostgresConnection:
    def __init__(self, pool: ThreadedConnectionPool, connection: PGConnection) -> None:
        self._pool = pool
        self._connection = connection
        self._released = False

    def __getattr__(self, name: str):
        return getattr(self._connection, name)

    def __enter__(self) -> "PooledPostgresConnection":
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            return bool(self._connection.__exit__(exc_type, exc, tb))
        finally:
            self.close()

    def close(self) -> None:
        if self._released:
            return
        self._pool.putconn(self._connection)
        self._released = True


class PostgresConnectionFactory:
    def __init__(self, settings: PostgresSettings | None = None) -> None:
        self._settings = settings or PostgresSettings()
        self._pool: ThreadedConnectionPool | None = None
        self._lock = threading.Lock()

    def __call__(self) -> PooledPostgresConnection:
        return self.create_connection()

    def _get_pool(self) -> ThreadedConnectionPool:
        if self._pool is not None:
            return self._pool
        with self._lock:
            if self._pool is not None:
                return self._pool
            self._settings.validate()
            try:
                self._pool = ThreadedConnectionPool(
                    minconn=self._settings.pool_minconn,
                    maxconn=self._settings.pool_maxconn,
                    host=self._settings.host,
                    port=self._settings.port,
                    dbname=self._settings.database,
                    user=self._settings.user,
                    password=self._settings.password,
                    sslmode=self._settings.sslmode,
                    connect_timeout=self._settings.connect_timeout,
                    application_name=self._settings.application_name,
                )
                return self._pool
            except psycopg2.Error as exc:
                LOGGER.exception(
                    "Failed to initialize PostgreSQL pool host=%s port=%s db=%s user=%s",
                    self._settings.host,
                    self._settings.port,
                    self._settings.database,
                    self._settings.user,
                )
                raise PostgresConnectionError("Could not initialize PostgreSQL connection pool") from exc

    def _reset_pool(self) -> None:
        with self._lock:
            old_pool = self._pool
            self._pool = None
        if old_pool is not None:
            try:
                old_pool.closeall()
            except Exception:
                pass
        LOGGER.warning(
            "PostgreSQL connection pool reset host=%s port=%s db=%s",
            self._settings.host,
            self._settings.port,
            self._settings.database,
        )

    def create_connection(self) -> PooledPostgresConnection:
        for attempt in range(2):
            pool = self._get_pool()
            try:
                conn = pool.getconn()
            except psycopg2.Error as exc:
                LOGGER.exception(
                    "Failed to acquire PostgreSQL connection from pool host=%s port=%s db=%s user=%s",
                    self._settings.host,
                    self._settings.port,
                    self._settings.database,
                    self._settings.user,
                )
                if attempt == 0:
                    self._reset_pool()
                    continue
                raise PostgresConnectionError("Could not acquire PostgreSQL connection from pool") from exc
            if conn.closed:
                try:
                    pool.putconn(conn, close=True)
                except Exception:
                    pass
                if attempt == 0:
                    self._reset_pool()
                    continue
                raise PostgresConnectionError("Could not acquire a live PostgreSQL connection after pool reset")
            return PooledPostgresConnection(pool, conn)
        raise PostgresConnectionError("Could not acquire PostgreSQL connection from pool")

    @contextmanager
    def connection(self) -> Iterator[PooledPostgresConnection]:
        conn = self.create_connection()
        try:
            yield conn
        finally:
            conn.close()


def create_postgres_connection_factory(
    settings: PostgresSettings | None = None,
) -> PostgresConnectionFactory:
    return PostgresConnectionFactory(settings=settings)
