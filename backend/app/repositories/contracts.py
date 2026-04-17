from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence

from backend.app.domain.models import Match, OddsQuote, Pick


class MatchRepository(Protocol):
    def get_match(self, match_id: str) -> Match | None:
        ...


class OddsRepository(Protocol):
    def list_odds_for_match(self, match_id: str) -> Sequence[OddsQuote]:
        ...


class PickRepository(Protocol):
    def list_picks_for_day(self, target_date: date) -> Sequence[Pick]:
        ...


class ResultRepository(Protocol):
    def settle_pick(self, pick_id: str, profit_units: float) -> None:
        ...
