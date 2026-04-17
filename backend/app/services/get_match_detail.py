from __future__ import annotations

from backend.app.core.cache import TTLCache
from backend.app.domain.models import Match, OddsQuote, Pick
from backend.app.repositories.contracts import MatchRepository, OddsRepository, PickRepository


class GetMatchDetailService:
    def __init__(self, matches: MatchRepository, odds: OddsRepository, picks: PickRepository, cache: TTLCache | None = None, ttl_seconds: int = 0) -> None:
        self._matches = matches
        self._odds = odds
        self._picks = picks
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    def get(self, match_id: str) -> tuple[Match | None, list[OddsQuote], list[Pick]]:
        def _load() -> tuple[Match | None, list[OddsQuote], list[Pick]]:
            match = self._matches.get_match(match_id)
            if match is None:
                return None, [], []
            return match, list(self._odds.list_odds_for_match(match_id)), list(self._picks.list_picks_for_match(match_id))

        if self._cache is None or self._ttl_seconds <= 0:
            return _load()
        return self._cache.get_or_set("match_detail", match_id, self._ttl_seconds, _load)
