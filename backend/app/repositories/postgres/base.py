from __future__ import annotations

from typing import Any, Callable


class PostgresRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def _connection(self) -> Any:
        return self._connection_factory()
