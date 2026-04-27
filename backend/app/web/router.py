from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.app.api.dependencies import get_dashboard_service, get_match_repository, get_pick_repository
from backend.app.core.time import local_today, to_local_datetime
from backend.app.repositories.contracts import MatchRepository, PickRepository
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


def _serialize_stored_match(match) -> dict:
    local_kickoff = to_local_datetime(match.kickoff_at)
    return {
        "match_id": match.id,
        "event_id": str(match.external_id or ""),
        "date": local_kickoff.strftime("%d/%m/%Y"),
        "match_date": str(local_kickoff.date()),
        "time": local_kickoff.strftime("%H:%M"),
        "home_team": match.home_team,
        "away_team": match.away_team,
        "home_team_raw": match.home_team,
        "away_team_raw": match.away_team,
        "fixture_label": f"{local_kickoff.strftime('%d/%m/%Y %H:%M')} | {match.home_team} vs {match.away_team}",
        "source": match.source or "DB",
    }


def _stored_league_dashboard(target_day: date, league: str, match_repository: MatchRepository) -> dict:
    matches = [
        match
        for match in match_repository.list_matches_for_day(target_day)
        if match.competition == league
    ]
    serialized = [_serialize_stored_match(match) for match in sorted(matches, key=lambda item: item.kickoff_at)]
    return {
        "league": league,
        "country": LEAGUE_CONFIGS.get(league, {}).get("country", "Internacional"),
        "match_count": len(serialized),
        "matches": serialized,
        "ranking": [],
    }


def _search_stored_matches(target_day: date, query: str, match_repository: MatchRepository) -> list[dict]:
    term = query.strip().lower()
    if not term:
        return []
    rows: list[dict] = []
    for match in match_repository.list_matches_for_day(target_day):
        home = str(match.home_team or "")
        away = str(match.away_team or "")
        if term not in home.lower() and term not in away.lower() and term not in f"{home} vs {away}".lower():
            continue
        local_kickoff = to_local_datetime(match.kickoff_at)
        rows.append(
            {
                "league": match.competition,
                "country": LEAGUE_CONFIGS.get(match.competition, {}).get("country", "Internacional"),
                "match": f"{home} vs {away}",
                "time": local_kickoff.strftime("%H:%M"),
                "fixture_label": f"{local_kickoff.strftime('%d/%m/%Y %H:%M')} | {home} vs {away}",
                "match_id": match.id,
            }
        )
    return rows[:50]


def _stored_daily_value_ranking(
    target_day: date,
    competition_view: str,
    match_repository: MatchRepository,
    pick_repository: PickRepository,
) -> list[dict]:
    expected = "Liga" if competition_view == "Ligas" else "Torneo"
    matches = list(match_repository.list_matches_for_day(target_day))
    match_map = {match.id: match for match in matches}
    grouped: dict[str, dict] = {}
    for pick in pick_repository.list_picks_for_day(target_day):
        match = match_map.get(pick.match_id)
        if match is None:
            continue
        league = match.competition
        if COMPETITION_TYPES.get(league, "Liga") != expected:
            continue
        bucket = grouped.setdefault(
            league,
            {
                "league": league,
                "country": LEAGUE_CONFIGS.get(league, {}).get("country", "Internacional"),
                "match_count": 0,
                "match_ids": set(),
                "picks": [],
            },
        )
        bucket["match_ids"].add(match.id)
        bucket["picks"].append(
            {
                "match": f"{match.home_team} vs {match.away_team}",
                "match_id": match.id,
                "market": pick.market,
                "prob": pick.probability,
                "fair_odds": pick.fair_odds,
                "offered_odds": pick.offered_odds,
                "edge": pick.edge,
                "confidence": None,
                "confidence_label": None,
                "sample_size": None,
            }
        )
    rows: list[dict] = []
    for bucket in grouped.values():
        bucket["match_count"] = len(bucket.pop("match_ids"))
        bucket["picks"].sort(key=lambda item: item["edge"], reverse=True)
        rows.append(bucket)
    return sorted(
        rows,
        key=lambda item: (item["picks"][0]["edge"] if item["picks"] else -999.0, item["league"]),
        reverse=True,
    )


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    day: date | None = Query(default=None),
    competition_view: str | None = Query(default="Ligas"),
    q: str | None = Query(default=None),
    match_repository: MatchRepository = Depends(get_match_repository),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    league_rows = _stored_league_rows(target_day, competition_view, match_repository) or _static_league_rows(competition_view)
    search_results = _search_stored_matches(target_day, q, match_repository) if q and q.strip() else []
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "day": target_day.isoformat(),
            "competition_view": competition_view,
            "league_rows": league_rows,
            "search_query": q or "",
            "search_results": search_results,
        },
    )


@router.get("/league/{league}", response_class=HTMLResponse)
def league_detail(
    league: str,
    request: Request,
    day: date | None = Query(default=None),
    competition_view: str | None = Query(default="Ligas"),
    match_repository: MatchRepository = Depends(get_match_repository),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    league_dashboard = _stored_league_dashboard(target_day, league, match_repository)
    return templates.TemplateResponse(
        request,
        "league_detail.html",
        {
            "day": target_day.isoformat(),
            "competition_view": competition_view,
            "league_dashboard": league_dashboard,
        },
    )


@router.get("/daily-value", response_class=HTMLResponse)
def daily_value(
    request: Request,
    day: date | None = Query(default=None),
    competition_view: str | None = Query(default="Ligas"),
    match_repository: MatchRepository = Depends(get_match_repository),
    pick_repository: PickRepository = Depends(get_pick_repository),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    ranking_groups = _stored_daily_value_ranking(target_day, competition_view, match_repository, pick_repository)
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
