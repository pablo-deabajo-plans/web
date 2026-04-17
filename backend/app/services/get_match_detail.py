from __future__ import annotations

from backend.app.domain.models import Match, OddsQuote, Pick
from backend.app.repositories.contracts import MatchRepository, OddsRepository, PickRepository


class GetMatchDetailService:
    def __init__(self, matches: MatchRepository, odds: OddsRepository, picks: PickRepository) -> None:
        self._matches = matches
        self._odds = odds
        self._picks = picks

    def get(self, match_id: str) -> tuple[Match | None, list[OddsQuote], list[Pick]]:
        match = self._matches.get_match(match_id)
        if match is None:
            return None, [], []
        return match, list(self._odds.list_odds_for_match(match_id)), list(self._picks.list_picks_for_match(match_id))
