from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.app.api.dependencies import get_dashboard_service, get_match_repository
from backend.app.core.time import local_today, to_local_datetime
from backend.app.repositories.contracts import MatchRepository
from backend.app.schemas.analysis import AnalysisRead
from backend.app.services.dashboard import COMPETITION_TYPES
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
from data.sources import LEAGUE_CONFIGS


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["pct"] = fmt_pct
templates.env.filters["num"] = fmt_num
templates.env.filters["edge"] = fmt_edge
templates.env.filters["safe_text"] = safe_text

router = APIRouter(include_in_schema=False)


def _normalize_competition_view(value: str | None) -> str:
    return "Torneos" if value == "Torneos" else "Ligas"


def _static_league_rows(competition_view: str) -> list[dict]:
    expected = "Liga" if competition_view == "Ligas" else "Torneo"
    rows = []
    for league, config in LEAGUE_CONFIGS.items():
        if COMPETITION_TYPES.get(league, "Liga") != expected:
            continue
        rows.append(
            {
                "league": league,
                "country": str(config.get("country", "Internacional")),
                "match_count": None,
            }
        )
    return sorted(rows, key=lambda item: (item["country"], item["league"]))


def _stored_league_rows(
    target_day: date,
    competition_view: str,
    match_repository: MatchRepository,
) -> list[dict]:
    expected = "Liga" if competition_view == "Ligas" else "Torneo"
    grouped: dict[str, dict] = {}
    for match in match_repository.list_matches_for_day(target_day):
        league = match.competition
        if COMPETITION_TYPES.get(league, "Liga") != expected:
            continue
        row = grouped.setdefault(
            league,
            {
                "league": league,
                "country": str(LEAGUE_CONFIGS.get(league, {}).get("country", "Internacional")),
                "match_count": 0,
                "matches_preview": [],
            },
        )
        row["match_count"] += 1
        if len(row["matches_preview"]) < 3:
            local_kickoff = to_local_datetime(match.kickoff_at)
            row["matches_preview"].append(
                {
                    "match_id": match.id,
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "time": local_kickoff.strftime("%H:%M"),
                }
            )
    return sorted(grouped.values(), key=lambda item: (item["country"], item["league"]))


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    day: date | None = Query(default=None),
    competition_view: str | None = Query(default="Ligas"),
    league: str | None = Query(default=None),
    q: str | None = Query(default=None),
    service: DashboardService = Depends(get_dashboard_service),
    match_repository: MatchRepository = Depends(get_match_repository),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    league_rows = _stored_league_rows(target_day, competition_view, match_repository) or _static_league_rows(competition_view)
    selected_league = service.get_league_dashboard(league=league, target_date=target_day) if league else None
    search_results = service.search_matches(target_date=target_day, query=q) if q and q.strip() else []
    return templates.TemplateResponse(
        request,
        "index.html",
        {
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
        request,
        "daily_value.html",
        {
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
        request,
        "match_detail.html",
        {
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
