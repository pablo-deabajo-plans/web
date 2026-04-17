from __future__ import annotations

from datetime import date, datetime, timezone

from backend.app.domain.models import Pick
from backend.app.domain.pricing import build_pick
from backend.app.repositories.contracts import PickRepository


class InMemoryPickRepository(PickRepository):
    def __init__(self, picks: list[Pick] | None = None) -> None:
        self._picks = picks or self._seed()

    def list_picks_for_day(self, target_date: date) -> list[Pick]:
        return [
            pick
            for pick in self._picks
            if pick.created_at is not None and pick.created_at.date() == target_date
        ]

    @staticmethod
    def _seed() -> list[Pick]:
        now = datetime.now(timezone.utc)
        return [
            build_pick(
                match_id="match-001",
                market="1X2",
                selection="Home",
                probability=0.56,
                offered_odds=2.10,
                provider="seed",
                created_at=now,
            ),
            build_pick(
                match_id="match-002",
                market="BTTS",
                selection="Yes",
                probability=0.48,
                offered_odds=1.90,
                provider="seed",
                created_at=now,
            ),
        ]
