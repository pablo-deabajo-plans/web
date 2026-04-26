from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.analysis import AnalysisRead


class LeagueSummaryRead(BaseModel):
    league: str
    country: str
    match_count: int = Field(ge=0)


class MatchSearchResultRead(BaseModel):
    league: str
    country: str
    match: str
    time: str
    fixture_label: str
    match_id: str


class LeagueDashboardMatchRead(BaseModel):
    match_id: str
    event_id: str
    date: str
    match_date: str
    time: str
    home_team: str
    away_team: str
    home_team_raw: str
    away_team_raw: str
    fixture_label: str
    source: str


class RankingItemRead(BaseModel):
    league: str | None = None
    country: str | None = None
    match: str
    match_id: str | None = None
    market: str
    prob: float = Field(ge=0.0, le=1.0)
    fair_odds: float = Field(gt=0.0)
    offered_odds: float = Field(gt=1.0)
    edge: float
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_label: str | None = None
    sample_size: int | None = Field(default=None, ge=0)
    provider: str | None = None


class LeagueDashboardRead(BaseModel):
    league: str
    country: str
    match_count: int = Field(ge=0)
    matches: list[LeagueDashboardMatchRead]
    ranking: list[RankingItemRead]


class OddsRowRead(BaseModel):
    market: str
    prob: float = Field(ge=0.0, le=1.0)
    fair_odds: float = Field(gt=0.0)
    offered_odds: float = Field(gt=1.0)
    edge: float
    provider: str | None = None


class SignalFlagRead(BaseModel):
    probability: float = Field(ge=0.0, le=1.0)
    highlight: bool


class MatchDashboardRead(BaseModel):
    match: LeagueDashboardMatchRead
    analysis: AnalysisRead
    insights: list[str]
    comparison_table: list[dict[str, str]]
    odds_rows: list[OddsRowRead]
    auto_odds: dict[str, dict[str, Any]]
    player_probabilities: list[dict[str, Any]]
    signal_flags: dict[str, SignalFlagRead]


class CompareOddsRowRequest(BaseModel):
    market: str
    prob: float = Field(ge=0.0, le=1.0)
    offered_odds: float = Field(gt=1.0)


class CompareOddsRequest(BaseModel):
    rows: list[CompareOddsRowRequest]


class CompareOddsRowRead(BaseModel):
    market: str
    prob: float = Field(ge=0.0, le=1.0)
    fair_odds: float = Field(gt=0.0)
    offered_odds: float = Field(gt=1.0)
    edge: float


class KellyRequest(BaseModel):
    market: str
    probability: float = Field(ge=0.0, le=1.0)
    offered_odds: float = Field(gt=1.0)
    bankroll: float = Field(gt=0.0)
    mode: str


class KellyResultRead(BaseModel):
    market: str
    probability: float = Field(ge=0.0, le=1.0)
    fair_odds: float = Field(gt=0.0)
    offered_odds: float = Field(gt=1.0)
    edge: float
    bankroll: float = Field(gt=0.0)
    mode: str
    stake_fraction: float = Field(ge=0.0)
    stake_units: float = Field(ge=0.0)


class DailyValueLeagueRankingRead(BaseModel):
    league: str
    country: str
    match_count: int = Field(ge=0)
    picks: list[RankingItemRead]
