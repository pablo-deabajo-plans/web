from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from backend.app.api.dependencies import get_auth_service, get_dashboard_service, get_match_repository, get_pick_repository
from backend.app.core import settings
from backend.app.core.time import local_today, to_local_datetime
from backend.app.domain.models import User
from backend.app.repositories.contracts import MatchRepository, PickRepository
from backend.app.services.auth import AuthError, AuthService
from backend.app.schemas.analysis import AnalysisRead
from backend.app.services.dashboard import COMPETITION_TYPES
from backend.app.services.dashboard import DashboardService
from backend.app.web.presenters import (
    MATCH_TABS,
    build_projection_distribution,
    build_match_executive_summary,
    flatten_player_rows,
    fmt_edge,
    fmt_num,
    fmt_pct,
    match_signal_cards,
    pick_label,
    projection_min_probability_options,
    projection_stat_options,
    safe_text,
    tab_label,
    top_value_rows,
)
from backend.app.web.plans import access_for_user, upgrade_feature_context
from data.sources import LEAGUE_CONFIGS


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["pct"] = fmt_pct
templates.env.filters["num"] = fmt_num
templates.env.filters["edge"] = fmt_edge
templates.env.filters["safe_text"] = safe_text

router = APIRouter(include_in_schema=False)
SESSION_COOKIE = "gordon_session"


def _current_user(request: Request, auth: AuthService) -> User | None:
    return auth.current_user(request.cookies.get(SESSION_COOKIE))


def _base_context(request: Request, auth: AuthService, **values) -> dict:
    current_user = _current_user(request, auth)
    plan_access = access_for_user(current_user)
    return {"current_user": current_user, "plan_access": plan_access, **values}


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=status.HTTP_303_SEE_OTHER)


def _safe_return_to(value: str | None) -> str:
    candidate = str(value or "/").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    return candidate


def _upgrade_response(
    request: Request,
    auth: AuthService,
    *,
    feature: str = "daily_value",
    return_to: str = "/",
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "upgrade.html",
        _base_context(
            request,
            auth,
            day=local_today().isoformat(),
            feature=upgrade_feature_context(feature),
            feature_key=feature,
            return_to=_safe_return_to(return_to),
        ),
    )


def _set_session_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.is_production_like,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
    )


def _clear_session_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(SESSION_COOKIE)


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


@router.get("/upgrade", response_class=HTMLResponse)
def upgrade_page(
    request: Request,
    feature: str | None = Query(default="daily_value"),
    return_to: str | None = Query(default="/"),
    auth: AuthService = Depends(get_auth_service),
):
    current_user = _current_user(request, auth)
    plan_access = access_for_user(current_user)
    if plan_access.is_pro:
        return _redirect(_safe_return_to(return_to))
    return _upgrade_response(request, auth, feature=feature or "daily_value", return_to=return_to or "/")


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request, auth: AuthService = Depends(get_auth_service)):
    return templates.TemplateResponse(
        request,
        "register.html",
        _base_context(request, auth, day=local_today().isoformat(), error="", gmail="", nombre=""),
    )


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    gmail: str = Form(...),
    nombre: str = Form(...),
    password: str = Form(...),
    auth: AuthService = Depends(get_auth_service),
):
    try:
        user = auth.register(gmail, nombre, password)
    except AuthError as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            _base_context(request, auth, day=local_today().isoformat(), error=str(exc), gmail=gmail, nombre=nombre),
            status_code=400,
        )
    response = _redirect("/account")
    _set_session_cookie(response, auth.create_session_token(user))
    return response


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, auth: AuthService = Depends(get_auth_service)):
    return templates.TemplateResponse(
        request,
        "login.html",
        _base_context(request, auth, day=local_today().isoformat(), error="", gmail=""),
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    gmail: str = Form(...),
    password: str = Form(...),
    auth: AuthService = Depends(get_auth_service),
):
    try:
        user = auth.authenticate(gmail, password, request.client.host if request.client else "")
    except AuthError as exc:
        return templates.TemplateResponse(
            request,
            "login.html",
            _base_context(request, auth, day=local_today().isoformat(), error=str(exc), gmail=gmail),
            status_code=401,
        )
    response = _redirect("/")
    _set_session_cookie(response, auth.create_session_token(user))
    return response


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...), auth: AuthService = Depends(get_auth_service)):
    try:
        auth.verify_csrf(request.cookies.get(SESSION_COOKIE), csrf_token)
    except AuthError:
        return _redirect("/account")
    response = _redirect("/")
    _clear_session_cookie(response)
    return response


@router.get("/account", response_class=HTMLResponse)
def account_form(request: Request, auth: AuthService = Depends(get_auth_service)):
    user = _current_user(request, auth)
    if user is None:
        return _redirect("/login")
    session = auth.read_session(request.cookies.get(SESSION_COOKIE))
    return templates.TemplateResponse(
        request,
        "account.html",
        _base_context(
            request,
            auth,
            day=local_today().isoformat(),
            user=user,
            csrf_token=session.csrf_token if session else "",
            profile_error="",
            profile_success="",
            password_error="",
            password_success="",
        ),
    )


@router.post("/account/profile", response_class=HTMLResponse)
def account_profile_submit(
    request: Request,
    csrf_token: str = Form(...),
    nombre: str = Form(...),
    auth: AuthService = Depends(get_auth_service),
):
    user = _current_user(request, auth)
    if user is None:
        return _redirect("/login")
    session = auth.read_session(request.cookies.get(SESSION_COOKIE))
    try:
        auth.verify_csrf(request.cookies.get(SESSION_COOKIE), csrf_token)
        user = auth.update_nombre(user, nombre)
        profile_error = ""
        profile_success = "Nombre actualizado."
    except AuthError as exc:
        profile_error = str(exc)
        profile_success = ""
    return templates.TemplateResponse(
        request,
        "account.html",
        _base_context(
            request,
            auth,
            day=local_today().isoformat(),
            user=user,
            csrf_token=session.csrf_token if session else "",
            profile_error=profile_error,
            profile_success=profile_success,
            password_error="",
            password_success="",
        ),
        status_code=400 if profile_error else 200,
    )


@router.post("/account/password", response_class=HTMLResponse)
def account_password_submit(
    request: Request,
    csrf_token: str = Form(...),
    current_password: str = Form(...),
    new_password: str = Form(...),
    auth: AuthService = Depends(get_auth_service),
):
    user = _current_user(request, auth)
    if user is None:
        return _redirect("/login")
    session = auth.read_session(request.cookies.get(SESSION_COOKIE))
    try:
        auth.verify_csrf(request.cookies.get(SESSION_COOKIE), csrf_token)
        user = auth.update_password(user, current_password, new_password)
        password_error = ""
        password_success = "Contraseña actualizada."
    except AuthError as exc:
        password_error = str(exc)
        password_success = ""
    return templates.TemplateResponse(
        request,
        "account.html",
        _base_context(
            request,
            auth,
            day=local_today().isoformat(),
            user=user,
            csrf_token=session.csrf_token if session else "",
            profile_error="",
            profile_success="",
            password_error=password_error,
            password_success=password_success,
        ),
        status_code=400 if password_error else 200,
    )


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
            },
        )
        row["match_count"] += 1
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


def _stored_league_ranking(
    target_day: date,
    league: str,
    match_repository: MatchRepository,
    pick_repository: PickRepository,
) -> list[dict]:
    matches = [
        match
        for match in match_repository.list_matches_for_day(target_day)
        if match.competition == league
    ]
    if not matches:
        return []

    match_map = {match.id: match for match in matches}
    ranking: list[dict] = []
    for pick in pick_repository.list_picks_for_day(target_day):
        match = match_map.get(pick.match_id)
        if match is None:
            continue
        ranking.append(
            {
                "match": f"{match.home_team} vs {match.away_team}",
                "match_id": match.id,
                "market": pick.market,
                "selection": pick.selection,
                "pick_label": pick_label(pick.market, pick.selection, f"{match.home_team} vs {match.away_team}"),
                "prob": pick.probability,
                "fair_odds": pick.fair_odds,
                "offered_odds": pick.offered_odds,
                "edge": pick.edge,
                "confidence": None,
                "confidence_label": None,
                "sample_size": None,
                "provider": pick.provider,
            }
        )
    ranking.sort(key=lambda item: item["edge"], reverse=True)
    return ranking[:10]


def _stored_league_dashboard(
    target_day: date,
    league: str,
    match_repository: MatchRepository,
    pick_repository: PickRepository,
) -> dict:
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
        "ranking": _stored_league_ranking(target_day, league, match_repository, pick_repository),
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
                "selection": pick.selection,
                "pick_label": pick_label(pick.market, pick.selection, f"{match.home_team} vs {match.away_team}"),
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
    auth: AuthService = Depends(get_auth_service),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    current_user = _current_user(request, auth)
    plan_access = access_for_user(current_user)
    league_rows = _stored_league_rows(target_day, competition_view, match_repository) or _static_league_rows(competition_view)
    league_rows = plan_access.filter_league_rows(league_rows)
    search_results = _search_stored_matches(target_day, q, match_repository) if q and q.strip() else []
    search_results = plan_access.filter_matches(search_results)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "current_user": current_user,
            "plan_access": plan_access,
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
    pick_repository: PickRepository = Depends(get_pick_repository),
    auth: AuthService = Depends(get_auth_service),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    current_user = _current_user(request, auth)
    plan_access = access_for_user(current_user)
    if not plan_access.can_view_league(league):
        return _upgrade_response(
            request,
            auth,
            feature="all_leagues",
            return_to=f"/league/{league}?day={target_day.isoformat()}&competition_view={competition_view}",
        )
    league_dashboard = _stored_league_dashboard(target_day, league, match_repository, pick_repository)
    if not plan_access.can_view_odds_value:
        league_dashboard = {**league_dashboard, "ranking": []}
    return templates.TemplateResponse(
        request,
        "league_detail.html",
        {
            "current_user": current_user,
            "plan_access": plan_access,
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
    auth: AuthService = Depends(get_auth_service),
):
    target_day = day or local_today()
    competition_view = _normalize_competition_view(competition_view)
    current_user = _current_user(request, auth)
    plan_access = access_for_user(current_user)
    if not plan_access.can_view_daily_value:
        return _upgrade_response(
            request,
            auth,
            feature="daily_value",
            return_to=f"/daily-value?day={target_day.isoformat()}&competition_view={competition_view}",
        )
    ranking_groups = (
        _stored_daily_value_ranking(target_day, competition_view, match_repository, pick_repository)
        if plan_access.can_view_daily_value
        else []
    )
    return templates.TemplateResponse(
        request,
        "daily_value.html",
        {
            "current_user": current_user,
            "plan_access": plan_access,
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
    projection_stat: str = Query(default="corners"),
    min_probability: float = Query(default=0.30, ge=0.05, le=0.95),
    service: DashboardService = Depends(get_dashboard_service),
    auth: AuthService = Depends(get_auth_service),
):
    current_user = _current_user(request, auth)
    plan_access = access_for_user(current_user)
    if not plan_access.can_view_league(league):
        return _upgrade_response(
            request,
            auth,
            feature="all_leagues",
            return_to=f"/match-detail/{match_id}?league={league}&day={day.isoformat()}",
        )
    requested_tab = tab if tab in dict(MATCH_TABS) else "summary"
    if requested_tab not in plan_access.allowed_match_tabs:
        return _upgrade_response(
            request,
            auth,
            feature="odds_value",
            return_to=f"/match-detail/{match_id}?league={league}&day={day.isoformat()}&tab={requested_tab}",
        )
    if projection_stat not in {item["key"] for item in projection_stat_options()}:
        projection_stat = "corners"
    if not plan_access.is_pro and requested_tab == "projection" and projection_stat != plan_access.coerce_projection_stat(projection_stat):
        return _upgrade_response(
            request,
            auth,
            feature="advanced_projection",
            return_to=f"/match-detail/{match_id}?league={league}&day={day.isoformat()}&tab=projection&projection_stat={projection_stat}",
        )
    payload = service.get_match_dashboard(league=league, target_date=day, match_id=match_id)
    analysis = AnalysisRead.from_domain(payload["analysis"]).model_dump()
    active_tab = plan_access.coerce_match_tab(requested_tab)
    locked_tab_label = tab_label(requested_tab) if requested_tab != active_tab else ""
    selected_projection_stat = plan_access.coerce_projection_stat(projection_stat)
    min_probability = plan_access.coerce_projection_min_probability(min_probability)
    odds_rows = payload["odds_rows"] if plan_access.can_view_odds_value else []
    top_edges = top_value_rows(odds_rows)
    player_rows = flatten_player_rows(payload["player_probabilities"])
    projection_distribution = build_projection_distribution(analysis, selected_projection_stat, min_probability)
    projection_distribution = plan_access.filter_projection_distribution(projection_distribution)
    return templates.TemplateResponse(
        request,
        "match_detail.html",
        {
            "current_user": current_user,
            "plan_access": plan_access,
            "day": day.isoformat(),
            "league": league,
            "match_id": match_id,
            "match": payload["match"],
            "analysis": analysis,
            "insights": payload["insights"],
            "comparison_table": payload["comparison_table"],
            "odds_rows": odds_rows,
            "top_edges": top_edges,
            "signal_cards": match_signal_cards(analysis),
            "executive_summary": build_match_executive_summary(analysis, odds_rows),
            "tabs": MATCH_TABS,
            "active_tab": active_tab,
            "active_tab_label": tab_label(active_tab),
            "locked_tab_label": locked_tab_label,
            "projection_stats": projection_stat_options(),
            "projection_min_probabilities": projection_min_probability_options(),
            "selected_projection_stat": selected_projection_stat,
            "selected_min_probability": projection_distribution["min_probability"],
            "projection_distribution": projection_distribution,
            "player_payload": payload["player_probabilities"],
            "player_rows": player_rows,
        },
    )
