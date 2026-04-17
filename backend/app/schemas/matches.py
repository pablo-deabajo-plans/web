from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.domain.models import Match, OddsQuote
from backend.app.schemas.picks import PickRead


class MatchRead(BaseModel):
    id: str
    competition: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    status: str
    source: str | None = None

    @classmethod
    def from_domain(cls, match: Match) -> "MatchRead":
        return cls(
            id=match.id,
            competition=match.competition,
            kickoff_at=match.kickoff_at,
            home_team=match.home_team,
            away_team=match.away_team,
            status=match.status,
            source=match.source,
        )


class OddsQuoteRead(BaseModel):
    id: str | None = None
    match_id: str
    market: str
    selection: str
    decimal_odds: float = Field(gt=1.0)
    sportsbook: str | None = None
    captured_at: datetime | None = None

    @classmethod
    def from_domain(cls, quote: OddsQuote) -> "OddsQuoteRead":
        return cls(
            id=quote.id,
            match_id=quote.match_id,
            market=quote.market,
            selection=quote.selection,
            decimal_odds=quote.decimal_odds,
            sportsbook=quote.sportsbook,
            captured_at=quote.captured_at,
        )


class MatchDetailRead(BaseModel):
    match: MatchRead
    odds: list[OddsQuoteRead]
    picks: list[PickRead]
