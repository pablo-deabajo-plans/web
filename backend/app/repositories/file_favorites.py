from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path


LOGGER = logging.getLogger(__name__)
DEFAULT_FAVORITES_FILE = Path("data/favorite_picks.json")


@dataclass(frozen=True)
class FavoritePickRecord:
    id: str
    saved_at: str
    liga: str
    match: str
    market: str
    prob: float
    fair_odds: float
    offered_odds: float
    edge: float
    kelly_pct: float
    stake_units: float


class FileFavoriteRepository:
    def __init__(self, path: Path = DEFAULT_FAVORITES_FILE) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def list_all(self) -> list[FavoritePickRecord]:
        if not self._path.exists():
            return []
        try:
            with self._path.open("r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Unable to read favorites from %s: %s", self._path, exc)
            return []

        if not isinstance(payload, list):
            return []

        items: list[FavoritePickRecord] = []
        for raw_item in payload:
            try:
                items.append(FavoritePickRecord(**raw_item))
            except TypeError:
                LOGGER.warning("Skipping invalid favorite payload in %s: %s", self._path, raw_item)
        return items

    def save(self, item: FavoritePickRecord) -> None:
        with self._lock:
            records = self.list_all()
            records.insert(0, item)
            self.replace_all(records[:30])

    def delete(self, favorite_id: str) -> bool:
        with self._lock:
            existing = self.list_all()
            remaining = [item for item in existing if item.id != favorite_id]
            if len(remaining) == len(existing):
                return False
            self.replace_all(remaining)
            return True

    def clear(self) -> None:
        self.replace_all([])

    def replace_all(self, items: list[FavoritePickRecord]) -> None:
        serialized = [asdict(item) for item in items]
        with self._path.open("w", encoding="utf-8") as file_handle:
            json.dump(serialized, file_handle, indent=2, ensure_ascii=True)
