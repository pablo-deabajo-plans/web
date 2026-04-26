from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.app.api.dependencies import get_dashboard_service
from backend.app.schemas.analysis import AnalysisRead
from backend.app.schemas.dashboard import (
    CompareOddsRequest,
    CompareOddsRowRead,
    DailyValueLeagueRankingRead,
    KellyRequest,
    KellyResultRead,
    LeagueDashboardRead,
    LeagueSummaryRead,
    MatchDashboardRead,
    MatchSearchResultRead,
)
from backend.app.services.dashboard import DashboardService


router = APIRouter()


@router.get("/leagues", response_model=list[LeagueSummaryRead])
def get_leagues(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    day: date = Query(...),
    competition_view: str | None = Query(default=None),
) -> list[LeagueSummaryRead]:
    return service.list_leagues(target_date=day, competition_view=competition_view)


@router.get("/search", response_model=list[MatchSearchResultRead])
def search_matches(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    day: date = Query(...),
    query: str = Query(..., min_length=1),
) -> list[MatchSearchResultRead]:
    return service.search_matches(target_date=day, query=query)


@router.get("/league/{league}", response_model=LeagueDashboardRead)
def get_league_dashboard(
    league: str,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    day: date = Query(...),
) -> LeagueDashboardRead:
    return service.get_league_dashboard(league=league, target_date=day)


@router.get("/daily-value-ranking", response_model=list[DailyValueLeagueRankingRead])
def get_daily_value_ranking(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    day: date = Query(...),
    competition_view: str | None = Query(default=None),
) -> list[DailyValueLeagueRankingRead]:
    return service.get_daily_value_ranking(target_date=day, competition_view=competition_view)


@router.get("/match/{match_id}", response_model=MatchDashboardRead)
def get_match_dashboard(
    match_id: str,
    league: str,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    day: date = Query(...),
    sportmonks_token: str | None = Header(default="", alias="X-Sportmonks-Token"),
) -> MatchDashboardRead:
    try:
        payload = service.get_match_dashboard(
            league=league,
            target_date=day,
            match_id=match_id,
            sportmonks_token=str(sportmonks_token or ""),
        )
        payload["analysis"] = AnalysisRead.from_domain(payload["analysis"])
        return MatchDashboardRead.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/compare-odds", response_model=list[CompareOddsRowRead])
def compare_odds(
    payload: CompareOddsRequest,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> list[CompareOddsRowRead]:
    return service.compare_odds(rows=[row.model_dump() for row in payload.rows])


@router.post("/kelly", response_model=KellyResultRead)
def calculate_kelly(
    payload: KellyRequest,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> KellyResultRead:
    return service.calculate_kelly(
        market=payload.market,
        probability=payload.probability,
        offered_odds=payload.offered_odds,
        bankroll=payload.bankroll,
        mode=payload.mode,
    )
