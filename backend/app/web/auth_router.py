from __future__ import annotations

import secrets
import sys

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse

from backend.app.api.dependencies import get_audit_log_repository, get_auth_service
from backend.app.core import settings
from backend.app.core.time import local_today
from backend.app.repositories.contracts import AuditLogRepository
from backend.app.services.auth import AuthError, AuthService
from backend.app.web._web_shared import (
    SESSION_COOKIE,
    _base_context,
    _current_user,
    _redirect,
    _safe_return_to,
    _upgrade_response,
    templates,
)
from backend.app.web.plans import access_for_user


router = APIRouter(include_in_schema=False)

_PRE_CSRF_COOKIE = "_csrf"


def _new_pre_csrf() -> str:
    return secrets.token_urlsafe(32)


def _set_pre_csrf_cookie(response, token: str) -> None:
    response.set_cookie(
        _PRE_CSRF_COOKIE, token, httponly=True,
        secure=settings.is_production_like, samesite="strict", max_age=3600,
    )


def _verify_pre_csrf(request: Request, form_token: str) -> bool:
    cookie = request.cookies.get(_PRE_CSRF_COOKIE, "")
    return bool(cookie) and secrets.compare_digest(cookie, form_token)


def _set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.is_production_like,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
    )


def _clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE)


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
    csrf_token = _new_pre_csrf()
    response = templates.TemplateResponse(
        request,
        "register.html",
        _base_context(request, auth, day=local_today().isoformat(), error="", gmail="", nombre="", csrf_token=csrf_token),
    )
    _set_pre_csrf_cookie(response, csrf_token)
    return response


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    gmail: str = Form(...),
    nombre: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    auth: AuthService = Depends(get_auth_service),
    audit: AuditLogRepository = Depends(get_audit_log_repository),
):
    if not _verify_pre_csrf(request, csrf_token):
        new_csrf = _new_pre_csrf()
        resp = templates.TemplateResponse(
            request,
            "register.html",
            _base_context(request, auth, day=local_today().isoformat(), error="Petición no válida.", gmail=gmail, nombre=nombre, csrf_token=new_csrf),
            status_code=403,
        )
        _set_pre_csrf_cookie(resp, new_csrf)
        return resp
    try:
        user = auth.register(gmail, nombre, password, client_key=request.client.host if request.client else "")
    except AuthError as exc:
        new_csrf = _new_pre_csrf()
        resp = templates.TemplateResponse(
            request,
            "register.html",
            _base_context(request, auth, day=local_today().isoformat(), error=str(exc), gmail=gmail, nombre=nombre, csrf_token=new_csrf),
            status_code=400,
        )
        _set_pre_csrf_cookie(resp, new_csrf)
        return resp
    response = _redirect("/account")
    _set_session_cookie(response, auth.create_session_token(user))
    try:
        audit.log(user.id, "register.success", {"gmail": user.gmail})
    except Exception:
        print("audit log failed", file=sys.stderr)
    return response


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(
    request: Request,
    token: str | None = Query(default=None),
    auth: AuthService = Depends(get_auth_service),
):
    if not token:
        return templates.TemplateResponse(
            request,
            "login.html",
            _base_context(request, auth, day=local_today().isoformat(), error="Enlace de verificación no válido.", gmail=""),
            status_code=400,
        )
    user = auth.verify_email_token(token)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            _base_context(request, auth, day=local_today().isoformat(), error="El enlace de verificación ha caducado o no es válido.", gmail=""),
            status_code=400,
        )
    return _redirect("/account")


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, auth: AuthService = Depends(get_auth_service)):
    csrf_token = _new_pre_csrf()
    response = templates.TemplateResponse(
        request,
        "login.html",
        _base_context(request, auth, day=local_today().isoformat(), error="", gmail="", csrf_token=csrf_token),
    )
    _set_pre_csrf_cookie(response, csrf_token)
    return response


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    gmail: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    auth: AuthService = Depends(get_auth_service),
    audit: AuditLogRepository = Depends(get_audit_log_repository),
):
    if not _verify_pre_csrf(request, csrf_token):
        new_csrf = _new_pre_csrf()
        resp = templates.TemplateResponse(
            request,
            "login.html",
            _base_context(request, auth, day=local_today().isoformat(), error="Petición no válida.", gmail=gmail, csrf_token=new_csrf),
            status_code=403,
        )
        _set_pre_csrf_cookie(resp, new_csrf)
        return resp
    try:
        user = auth.authenticate(gmail, password, request.client.host if request.client else "")
    except AuthError as exc:
        try:
            audit.log(None, "login.failure", {"gmail": gmail, "reason": str(exc)})
        except Exception:
            print("audit log failed", file=sys.stderr)
        new_csrf = _new_pre_csrf()
        resp = templates.TemplateResponse(
            request,
            "login.html",
            _base_context(request, auth, day=local_today().isoformat(), error=str(exc), gmail=gmail, csrf_token=new_csrf),
            status_code=401,
        )
        _set_pre_csrf_cookie(resp, new_csrf)
        return resp
    try:
        audit.log(user.id, "login.success", {"gmail": user.gmail})
    except Exception:
        print("audit log failed", file=sys.stderr)
    response = _redirect("/")
    _set_session_cookie(response, auth.create_session_token(user))
    return response


@router.post("/logout")
def logout(
    request: Request,
    csrf_token: str = Form(...),
    auth: AuthService = Depends(get_auth_service),
    audit: AuditLogRepository = Depends(get_audit_log_repository),
):
    try:
        auth.verify_csrf(request.cookies.get(SESSION_COOKIE), csrf_token)
    except AuthError:
        return _redirect("/account")
    user = _current_user(request, auth)
    auth.revoke_session(request.cookies.get(SESSION_COOKIE))
    try:
        audit.log(user.id if user else None, "logout", {})
    except Exception:
        print("audit log failed", file=sys.stderr)
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
