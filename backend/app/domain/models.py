from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


MATCH_STATUS_SCHEDULED = "scheduled"
MATCH_STATUS_LIVE = "live"
MATCH_STATUS_FINISHED = "finished"
MATCH_STATUS_CANCELLED = "cancelled"
MATCH_STATUS_POSTPONED = "postponed"
MATCH_STATUS_ABANDONED = "abandoned"

MATCH_STATUSES = {
    MATCH_STATUS_SCHEDULED,
    MATCH_STATUS_LIVE,
    MATCH_STATUS_FINISHED,
    MATCH_STATUS_CANCELLED,
    MATCH_STATUS_POSTPONED,
    MATCH_STATUS_ABANDONED,
}

ACTIVE_MATCH_STATUSES = {MATCH_STATUS_SCHEDULED, MATCH_STATUS_LIVE}
VOID_MATCH_STATUSES = {
    MATCH_STATUS_CANCELLED,
    MATCH_STATUS_POSTPONED,
    MATCH_STATUS_ABANDONED,
}
SETTLED_MATCH_STATUSES = {MATCH_STATUS_FINISHED, *VOID_MATCH_STATUSES}


@dataclass(frozen=True)
class Fixture:
    id: str
    competition: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    external_id: str | None = None
    status: str = "scheduled"
    source: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    home_corners: float | None = None
    away_corners: float | None = None
    home_shots: float | None = None
    away_shots: float | None = None
    home_shots_on_target: float | None = None
    away_shots_on_target: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class MatchResult:
    fixture_id: str
    status: str
    home_score: int
    away_score: int
    home_corners: float | None = None
    away_corners: float | None = None
    home_shots: float | None = None
    away_shots: float | None = None
    home_shots_on_target: float | None = None
    away_shots_on_target: float | None = None
    settled_at: datetime | None = None


@dataclass(frozen=True)
class OddsSnapshot:
    match_id: str
    market: str
    selection: str
    decimal_odds: float
    sportsbook: str | None = None
    captured_at: datetime | None = None
    id: str | None = None


@dataclass(frozen=True)
class PickRecommendation:
    id: str
    match_id: str
    market: str
    selection: str
    probability: float
    fair_odds: float
    offered_odds: float
    edge: float
    stake_fraction: float
    stake_units: float | None = None
    closing_odds: float | None = None
    clv_absolute: float | None = None
    clv_percent: float | None = None
    status: str = "open"
    provider: str | None = None
    analysis_id: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class SettledPick:
    id: str
    pick_id: str
    status: str
    stake_units: float
    profit_units: float
    settled_selection: str | None = None
    settled_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class User:
    id: str
    gmail: str
    nombre: str
    password_hash: str
    plan: str = "free"
    password_changed_at: datetime | None = None
    email_verified_at: datetime | None = None


@dataclass(frozen=True)
class AnalysisResult:
    home_win: float
    draw: float
    away_win: float
    both_teams_score: float
    over_2_5_goals: float
    under_2_5_goals: float
    home_over_1_5_goals: float
    away_over_1_5_goals: float
    home_clean_sheet: float
    away_clean_sheet: float
    home_corners: float
    away_corners: float
    over_9_5_corners: float
    home_cards: float
    away_cards: float
    total_cards: float
    home_shots: float
    away_shots: float
    home_shots_on_target: float
    away_shots_on_target: float
    home_over_3_5_corners: float
    away_over_3_5_corners: float
    home_over_4_5_corners: float
    away_over_4_5_corners: float
    total_goals: float
    total_corners: float
    top_scores: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    most_likely_score: str = "0-0"

    def __getitem__(self, key: str) -> Any:
        return self.to_legacy_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_legacy_dict().get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self.to_legacy_dict()

    def to_legacy_dict(self) -> dict[str, Any]:
        return {
            "1": self.home_win,
            "X": self.draw,
            "2": self.away_win,
            "BTTS": self.both_teams_score,
            "O25": self.over_2_5_goals,
            "U25": self.under_2_5_goals,
            "Home_Over15": self.home_over_1_5_goals,
            "Away_Over15": self.away_over_1_5_goals,
            "Home_CleanSheet": self.home_clean_sheet,
            "Away_CleanSheet": self.away_clean_sheet,
            "Corn_Home": self.home_corners,
            "Corn_Away": self.away_corners,
            "Over9.5_Corn": self.over_9_5_corners,
            "Cards_Home": self.home_cards,
            "Cards_Away": self.away_cards,
            "Total_Cards": self.total_cards,
            "Shots_Home": self.home_shots,
            "Shots_Away": self.away_shots,
            "ShotsOnTarget_Home": self.home_shots_on_target,
            "ShotsOnTarget_Away": self.away_shots_on_target,
            "Home_Over35_Corn": self.home_over_3_5_corners,
            "Away_Over35_Corn": self.away_over_3_5_corners,
            "Home_Over45_Corn": self.home_over_4_5_corners,
            "Away_Over45_Corn": self.away_over_4_5_corners,
            "Total_Goals": self.total_goals,
            "Total_Corners": self.total_corners,
            "TopScores": list(self.top_scores),
            "Marcador": self.most_likely_score,
        }

    @classmethod
    def from_legacy_dict(cls, payload: dict[str, Any]) -> "AnalysisResult":
        return cls(
            home_win=float(payload["1"]),
            draw=float(payload["X"]),
            away_win=float(payload["2"]),
            both_teams_score=float(payload["BTTS"]),
            over_2_5_goals=float(payload["O25"]),
            under_2_5_goals=float(payload["U25"]),
            home_over_1_5_goals=float(payload["Home_Over15"]),
            away_over_1_5_goals=float(payload["Away_Over15"]),
            home_clean_sheet=float(payload["Home_CleanSheet"]),
            away_clean_sheet=float(payload["Away_CleanSheet"]),
            home_corners=float(payload["Corn_Home"]),
            away_corners=float(payload["Corn_Away"]),
            over_9_5_corners=float(payload["Over9.5_Corn"]),
            home_cards=float(payload["Cards_Home"]),
            away_cards=float(payload["Cards_Away"]),
            total_cards=float(payload["Total_Cards"]),
            home_shots=float(payload["Shots_Home"]),
            away_shots=float(payload["Shots_Away"]),
            home_shots_on_target=float(payload["ShotsOnTarget_Home"]),
            away_shots_on_target=float(payload["ShotsOnTarget_Away"]),
            home_over_3_5_corners=float(payload["Home_Over35_Corn"]),
            away_over_3_5_corners=float(payload["Away_Over35_Corn"]),
            home_over_4_5_corners=float(payload["Home_Over45_Corn"]),
            away_over_4_5_corners=float(payload["Away_Over45_Corn"]),
            total_goals=float(payload["Total_Goals"]),
            total_corners=float(payload["Total_Corners"]),
            top_scores=tuple(tuple(item) for item in payload.get("TopScores", [])),
            most_likely_score=str(payload.get("Marcador", "0-0")),
        )


@dataclass(frozen=True)
class AnalysisMarket:
    name: str
    prob: float

    @property
    def nombre(self) -> str:
        return self.name

    def __getitem__(self, key: str) -> Any:
        if key in ("name", "nombre"):
            return self.name
        if key == "prob":
            return self.prob
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key in ("name", "nombre"):
            return self.name
        if key == "prob":
            return self.prob
        return default

    @classmethod
    def from_legacy_dict(cls, payload: dict[str, Any]) -> "AnalysisMarket":
        return cls(name=str(payload.get("name") or payload["nombre"]), prob=float(payload["prob"]))


@dataclass(frozen=True)
class AnalysisSnapshot:
    liga: str
    local: str
    visitante: str
    local_raw: str
    visitante_raw: str
    match_date: datetime | date | None
    match_label: str
    resultado: AnalysisResult
    stats_local: dict[str, Any]
    stats_visitante: dict[str, Any]
    h2h: dict[str, Any]
    xg_local: float
    xg_visitante: float
    xc_local: float
    xc_visitante: float
    xt_local: float
    xt_visitante: float
    bonus_eliminatoria_local: float
    penalizacion_eliminatoria_visitante: float
    mercados: tuple[AnalysisMarket, ...] = field(default_factory=tuple)
    trace: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __getitem__(self, key: str) -> Any:
        return self.to_legacy_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_legacy_dict().get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self.to_legacy_dict()

    def to_legacy_dict(self) -> dict[str, Any]:
        return {
            "liga": self.liga,
            "local": self.local,
            "visitante": self.visitante,
            "local_raw": self.local_raw,
            "visitante_raw": self.visitante_raw,
            "match_date": self.match_date,
            "match_label": self.match_label,
            "resultado": self.resultado.to_legacy_dict(),
            "stats_local": self.stats_local,
            "stats_visitante": self.stats_visitante,
            "h2h": self.h2h,
            "xg_local": self.xg_local,
            "xg_visitante": self.xg_visitante,
            "xc_local": self.xc_local,
            "xc_visitante": self.xc_visitante,
            "xt_local": self.xt_local,
            "xt_visitante": self.xt_visitante,
            "bonus_eliminatoria_local": self.bonus_eliminatoria_local,
            "penalizacion_eliminatoria_visitante": self.penalizacion_eliminatoria_visitante,
            "mercados": [{"nombre": market.name, "prob": market.prob} for market in self.mercados],
            "trace": self.trace,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_legacy_dict(cls, payload: dict[str, Any]) -> "AnalysisSnapshot":
        return cls(
            liga=str(payload["liga"]),
            local=str(payload["local"]),
            visitante=str(payload["visitante"]),
            local_raw=str(payload.get("local_raw", payload["local"])),
            visitante_raw=str(payload.get("visitante_raw", payload["visitante"])),
            match_date=payload.get("match_date"),
            match_label=str(payload.get("match_label", "")),
            resultado=AnalysisResult.from_legacy_dict(dict(payload["resultado"])),
            stats_local=dict(payload.get("stats_local") or {}),
            stats_visitante=dict(payload.get("stats_visitante") or {}),
            h2h=dict(payload.get("h2h") or {}),
            xg_local=float(payload.get("xg_local", 0.0)),
            xg_visitante=float(payload.get("xg_visitante", 0.0)),
            xc_local=float(payload.get("xc_local", 0.0)),
            xc_visitante=float(payload.get("xc_visitante", 0.0)),
            xt_local=float(payload.get("xt_local", 0.0)),
            xt_visitante=float(payload.get("xt_visitante", 0.0)),
            bonus_eliminatoria_local=float(payload.get("bonus_eliminatoria_local", 1.0)),
            penalizacion_eliminatoria_visitante=float(payload.get("penalizacion_eliminatoria_visitante", 0.0)),
            mercados=tuple(AnalysisMarket.from_legacy_dict(item) for item in payload.get("mercados", [])),
            trace=dict(payload.get("trace") or {}),
            timestamp=str(payload.get("timestamp", "")),
        )


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


Match = Fixture
OddsQuote = OddsSnapshot
Pick = PickRecommendation
Result = SettledPick
Analysis = AnalysisSnapshot
