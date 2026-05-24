from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.domain.models import Analysis, AnalysisMarket, AnalysisResult


class AnalysisResultRead(BaseModel):
    home_win: float = Field(alias="1", ge=0.0, le=1.0)
    draw: float = Field(alias="X", ge=0.0, le=1.0)
    away_win: float = Field(alias="2", ge=0.0, le=1.0)
    both_teams_score: float = Field(alias="BTTS", ge=0.0, le=1.0)
    over_2_5_goals: float = Field(alias="O25", ge=0.0, le=1.0)
    under_2_5_goals: float = Field(alias="U25", ge=0.0, le=1.0)
    home_over_1_5_goals: float = Field(alias="Home_Over15", ge=0.0, le=1.0)
    away_over_1_5_goals: float = Field(alias="Away_Over15", ge=0.0, le=1.0)
    home_clean_sheet: float = Field(alias="Home_CleanSheet", ge=0.0, le=1.0)
    away_clean_sheet: float = Field(alias="Away_CleanSheet", ge=0.0, le=1.0)
    home_corners: float = Field(alias="Corn_Home")
    away_corners: float = Field(alias="Corn_Away")
    over_9_5_corners: float = Field(alias="Over9.5_Corn", ge=0.0, le=1.0)
    home_cards: float = Field(alias="Cards_Home")
    away_cards: float = Field(alias="Cards_Away")
    total_cards: float = Field(alias="Total_Cards")
    home_shots: float = Field(alias="Shots_Home")
    away_shots: float = Field(alias="Shots_Away")
    home_shots_on_target: float = Field(alias="ShotsOnTarget_Home")
    away_shots_on_target: float = Field(alias="ShotsOnTarget_Away")
    home_over_3_5_corners: float = Field(alias="Home_Over35_Corn", ge=0.0, le=1.0)
    away_over_3_5_corners: float = Field(alias="Away_Over35_Corn", ge=0.0, le=1.0)
    home_over_4_5_corners: float = Field(alias="Home_Over45_Corn", ge=0.0, le=1.0)
    away_over_4_5_corners: float = Field(alias="Away_Over45_Corn", ge=0.0, le=1.0)
    total_goals: float = Field(alias="Total_Goals")
    total_corners: float = Field(alias="Total_Corners")
    top_scores: list[tuple[str, int]] = Field(alias="TopScores")
    most_likely_score: str = Field(alias="Marcador")

    @classmethod
    def from_domain(cls, result: AnalysisResult) -> "AnalysisResultRead":
        return cls.model_validate(result.to_legacy_dict())


class AnalysisMarketRead(BaseModel):
    nombre: str
    prob: float = Field(ge=0.0, le=1.0)

    @classmethod
    def from_domain(cls, market: AnalysisMarket) -> "AnalysisMarketRead":
        return cls(nombre=market.name, prob=market.prob)


class AnalysisRead(BaseModel):
    liga: str
    local: str
    visitante: str
    local_raw: str
    visitante_raw: str
    match_date: datetime | date | None = None
    match_label: str
    resultado: AnalysisResultRead
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
    mercados: list[AnalysisMarketRead]
    trace: dict[str, Any]
    timestamp: str
    model_disclaimer: str = "Model weights are expert estimates; edge values are directional only and have not been backtested against historical ROI."

    @classmethod
    def from_domain(cls, analysis: Analysis) -> "AnalysisRead":
        return cls(
            liga=analysis.liga,
            local=analysis.local,
            visitante=analysis.visitante,
            local_raw=analysis.local_raw,
            visitante_raw=analysis.visitante_raw,
            match_date=analysis.match_date,
            match_label=analysis.match_label,
            resultado=AnalysisResultRead.from_domain(analysis.resultado),
            stats_local=analysis.stats_local,
            stats_visitante=analysis.stats_visitante,
            h2h=analysis.h2h,
            xg_local=analysis.xg_local,
            xg_visitante=analysis.xg_visitante,
            xc_local=analysis.xc_local,
            xc_visitante=analysis.xc_visitante,
            xt_local=analysis.xt_local,
            xt_visitante=analysis.xt_visitante,
            bonus_eliminatoria_local=analysis.bonus_eliminatoria_local,
            penalizacion_eliminatoria_visitante=analysis.penalizacion_eliminatoria_visitante,
            mercados=[AnalysisMarketRead.from_domain(item) for item in analysis.mercados],
            trace=analysis.trace,
            timestamp=analysis.timestamp,
        )
