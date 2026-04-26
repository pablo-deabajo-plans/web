from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from backend.app.core.time import utc_now
from backend.app.repositories.file_favorites import FavoritePickRecord, FileFavoriteRepository


class FavoritesService:
    def __init__(self, repository: FileFavoriteRepository) -> None:
        self._repository = repository

    def list_payload(self) -> dict:
        items = self._repository.list_all()
        return {
            "items": [asdict(item) for item in items],
            "summary": self._summarize(items),
        }

    def create(self, payload: dict) -> dict:
        record = FavoritePickRecord(
            id=str(uuid4()),
            saved_at=utc_now().strftime("%Y-%m-%d %H:%M UTC"),
            liga=str(payload["liga"]),
            match=str(payload["match"]),
            market=str(payload["market"]),
            prob=float(payload["prob"]),
            fair_odds=float(payload["fair_odds"]),
            offered_odds=float(payload["offered_odds"]),
            edge=float(payload["edge"]),
            kelly_pct=float(payload["kelly_pct"]),
            stake_units=float(payload["stake_units"]),
        )
        self._validate(record)
        self._repository.save(record)
        return self.list_payload()

    def delete(self, favorite_id: str) -> dict | None:
        deleted = self._repository.delete(favorite_id)
        if not deleted:
            return None
        return self.list_payload()

    def clear(self) -> dict:
        self._repository.clear()
        return self.list_payload()

    @staticmethod
    def _summarize(items: list[FavoritePickRecord]) -> dict:
        total_stake = sum(item.stake_units for item in items)
        avg_edge = sum(item.edge for item in items) / len(items) if items else 0.0
        avg_probability = sum(item.prob for item in items) / len(items) if items else 0.0
        return {
            "count": len(items),
            "total_stake_units": total_stake,
            "average_edge": avg_edge,
            "average_probability": avg_probability,
        }

    @staticmethod
    def _validate(record: FavoritePickRecord) -> None:
        if not 0.0 <= record.prob <= 1.0:
            raise ValueError("Favorite probability must be between 0 and 1")
        if record.offered_odds <= 1.0:
            raise ValueError("Favorite offered odds must be greater than 1")
        if record.fair_odds <= 0.0:
            raise ValueError("Favorite fair odds must be greater than 0")
        if record.stake_units < 0.0:
            raise ValueError("Favorite stake must be non-negative")
