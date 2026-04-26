from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.app.api.dependencies import get_dashboard_service
from backend.app.core.time import local_today
from backend.app.schemas.analysis import AnalysisRead
from backend.app.services.dashboard import DashboardService
from backend.app.web.presenters import (
    MATCH_TABS,
    build_match_executive_summary,
    flatten_player_rows,
    fmt_edge,
    fmt_num,
    fmt_pct,
    match_signal_cards,
    safe_text,
    tab_label,
    top_value_rows,
)


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["pct"] = fmt_pct
templates.env.filters["num"] = fmt_num
templates.env.filters["edge"] = fmt_edge
templates.env.filters["safe_text"] = safe_text

router = APIRouter(include_in_schema=False)


def _normalize_competition_view(value: str | None) -> str:
    return "Torneos" if value == "Torneos" else "Ligas"


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    day: date | None = Query(default=None),
    competition_view: str | None = Query(default="Ligas"),
    league: str | None = Query(default=None),
    q: str | None = Query(default=None),
    service: DashboardService = Depends(get_dashboard_service),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    league_rows = service.list_leagues(target_date=target_day, competition_view=competition_view)
    selected_league = service.get_league_dashboard(league=league, target_date=target_day) if league else None
    search_results = service.search_matches(target_date=target_day, query=q) if q and q.strip() else []
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "day": target_day.isoformat(),
            "competition_view": competition_view,
            "league_rows": league_rows,
            "selected_league": selected_league,
            "search_query": q or "",
            "search_results": search_results,
        },
    )


@router.get("/daily-value", response_class=HTMLResponse)
def daily_value(
    request: Request,
    day: date | None = Query(default=None),
    competition_view: str | None = Query(default="Ligas"),
    service: DashboardService = Depends(get_dashboard_service),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    ranking_groups = service.get_daily_value_ranking(target_date=target_day, competition_view=competition_view)
    return templates.TemplateResponse(
        "daily_value.html",
        {
            "request": request,
            "day": target_day.isoformat(),
            "competition_view": competition_view,
            "ranking_groups": ranking_groups,
        },
    )


@router.get("/match-detail/{match_id}", response_class=HTMLResponse)
def match_detail(
    match_id: str,
    request: Request,
    league: str = Query(...),
    day: date = Query(...),
    tab: str = Query(default="summary"),
    service: DashboardService = Depends(get_dashboard_service),
):
    payload = service.get_match_dashboard(league=league, target_date=day, match_id=match_id)
    analysis = AnalysisRead.from_domain(payload["analysis"]).model_dump()
    active_tab = tab if tab in dict(MATCH_TABS) else "summary"
    top_edges = top_value_rows(payload["odds_rows"])
    player_rows = flatten_player_rows(payload["player_probabilities"])
    return templates.TemplateResponse(
        "match_detail.html",
        {
            "request": request,
            "day": day.isoformat(),
            "league": league,
            "match_id": match_id,
            "match": payload["match"],
            "analysis": analysis,
            "insights": payload["insights"],
            "comparison_table": payload["comparison_table"],
            "odds_rows": payload["odds_rows"],
            "top_edges": top_edges,
            "signal_cards": match_signal_cards(analysis),
            "executive_summary": build_match_executive_summary(analysis, payload["odds_rows"]),
            "tabs": MATCH_TABS,
            "active_tab": active_tab,
            "active_tab_label": tab_label(active_tab),
            "player_payload": payload["player_probabilities"],
            "player_rows": player_rows,
            "auto_odds": payload["auto_odds"],
        },
    )
