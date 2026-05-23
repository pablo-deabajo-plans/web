from __future__ import annotations

from pathlib import Path

from fastapi import Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from backend.app.core import settings
from backend.app.core.time import local_today
from backend.app.domain.models import User
from backend.app.services.auth import AuthService
from backend.app.web.presenters import fmt_edge, fmt_num, fmt_pct, safe_text
from backend.app.web.plans import access_for_user, upgrade_feature_context


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["pct"] = fmt_pct
templates.env.filters["num"] = fmt_num
templates.env.filters["edge"] = fmt_edge
templates.env.filters["safe_text"] = safe_text

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
