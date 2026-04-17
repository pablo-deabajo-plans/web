from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class Match:
    id: str
    competition: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    status: str = "scheduled"
    source: str | None = None


@dataclass(frozen=True)
class OddsQuote:
    match_id: str
    market: str
    selection: str
    decimal_odds: float
    sportsbook: str | None = None
    captured_at: datetime | None = None
    id: str | None = None


@dataclass(frozen=True)
class Pick:
    id: str
    match_id: str
    market: str
    selection: str
    probability: float
    fair_odds: float
    offered_odds: float
    edge: float
    stake_fraction: float
    provider: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class Result:
    id: str
    pick_id: str
    status: str
    stake_units: float
    profit_units: float
    settled_at: datetime | None = None


@dataclass(frozen=True)
class User:
    id: str
    email: str
    created_at: datetime
    is_active: bool = True


@dataclass(frozen=True)
class Analysis:
    match_id: str
    generated_at: datetime
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    expected_home_goals: float
    expected_away_goals: float
    competition: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    model_version: str = "legacy-poisson-v1"
    markets: tuple[Pick, ...] = field(default_factory=tuple)
    trace: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PlayerProp:
    match_id: str
    player_id: str
    player_name: str
    metric: str
    line: float
    probability: float
    expected_value: float
    confidence_label: str
    id: str | None = None
    generated_at: datetime | None = None


@dataclass(frozen=True)
class DailyPicksQuery:
    target_date: date
    limit: int = 10
