from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], CacheEntry] = {}
        self._lock = Lock()

    def get_or_set(self, namespace: str, key: str, ttl_seconds: int, loader: Callable[[], T]) -> T:
        cache_key = (namespace, key)
        now = monotonic()
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is not None and entry.expires_at > now:
                return entry.value
        value = loader()
        with self._lock:
            self._entries[cache_key] = CacheEntry(value=value, expires_at=now + ttl_seconds)
        return value

    def clear(self, namespace: str | None = None) -> None:
        with self._lock:
            if namespace is None:
                self._entries.clear()
                return
            keys = [key for key in self._entries if key[0] == namespace]
            for key in keys:
                self._entries.pop(key, None)
