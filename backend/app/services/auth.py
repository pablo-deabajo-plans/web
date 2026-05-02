from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import secrets
import time
from uuid import uuid4

import bcrypt

from backend.app.domain.models import User
from backend.app.repositories.contracts import UserRepository


class AuthError(ValueError):
    pass


class RateLimitError(AuthError):
    pass


@dataclass(frozen=True)
class SessionData:
    user_id: str
    expires_at: datetime
    csrf_token: str


_LOGIN_FAILURES: dict[str, list[float]] = {}


def normalize_gmail(value: str) -> str:
    return str(value or "").strip().lower()


def validate_gmail(value: str) -> str:
    gmail = normalize_gmail(value)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", gmail):
        raise AuthError("Introduce un correo valido.")
    return gmail


def validate_nombre(value: str) -> str:
    nombre = str(value or "").strip()
    if len(nombre) < 2 or len(nombre) > 40:
        raise AuthError("El nombre debe tener entre 2 y 40 caracteres.")
    return nombre


def validate_password(value: str) -> str:
    password = str(value or "")
    if len(password) < 10:
        raise AuthError("La contraseña debe tener al menos 10 caracteres.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise AuthError("La contraseña debe combinar letras y numeros.")
    return password


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


class AuthService:
    def __init__(self, users: UserRepository, session_secret: str, session_ttl_seconds: int) -> None:
        self._users = users
        self._session_secret = session_secret
        self._session_ttl_seconds = session_ttl_seconds

    def register(self, gmail: str, nombre: str, password: str) -> User:
        gmail = validate_gmail(gmail)
        nombre = validate_nombre(nombre)
        password = validate_password(password)
        if self._users.get_by_gmail(gmail) is not None:
            raise AuthError("Ya existe una cuenta con ese correo.")
        user = User(
            id=str(uuid4()),
            gmail=gmail,
            nombre=nombre,
            password_hash=hash_password(password),
            plan="free",
        )
        self._users.create_user(user)
        return user

    def authenticate(self, gmail: str, password: str, client_key: str = "") -> User:
        gmail = normalize_gmail(gmail)
        self._check_rate_limit(gmail, client_key)
        user = self._users.get_by_gmail(gmail)
        if user is None or not verify_password(password, user.password_hash):
            self._record_failure(gmail, client_key)
            raise AuthError("Credenciales incorrectas.")
        self._clear_failures(gmail, client_key)
        return user

    def update_nombre(self, user: User, nombre: str) -> User:
        return self._users.update_nombre(user.id, validate_nombre(nombre))

    def update_password(self, user: User, current_password: str, new_password: str) -> User:
        if not verify_password(current_password, user.password_hash):
            raise AuthError("La contraseña actual no es correcta.")
        return self._users.update_password_hash(user.id, hash_password(validate_password(new_password)))

    def create_session_token(self, user: User) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user.id,
            "exp": int((now + timedelta(seconds=self._session_ttl_seconds)).timestamp()),
            "csrf": secrets.token_urlsafe(24),
        }
        return self._sign_payload(payload)

    def read_session(self, token: str | None) -> SessionData | None:
        if not token:
            return None
        payload = self._read_payload(token)
        if payload is None:
            return None
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        return SessionData(user_id=str(payload["sub"]), expires_at=expires_at, csrf_token=str(payload["csrf"]))

    def current_user(self, token: str | None) -> User | None:
        session = self.read_session(token)
        if session is None:
            return None
        return self._users.get_by_id(session.user_id)

    def verify_csrf(self, token: str | None, csrf_token: str | None) -> None:
        session = self.read_session(token)
        if session is None or not csrf_token or not secrets.compare_digest(session.csrf_token, csrf_token):
            raise AuthError("Sesion no valida.")

    def _sign_payload(self, payload: dict) -> str:
        body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
        signature = hmac.new(self._session_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{body}.{signature}"

    def _read_payload(self, token: str) -> dict | None:
        if not self._session_secret:
            return None
        try:
            body, signature = token.split(".", 1)
        except ValueError:
            return None
        expected = hmac.new(self._session_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(signature, expected):
            return None
        try:
            return json.loads(base64.urlsafe_b64decode(body.encode("ascii")))
        except (ValueError, json.JSONDecodeError):
            return None

    def _rate_key(self, gmail: str, client_key: str) -> str:
        return f"{gmail}:{client_key}"

    def _check_rate_limit(self, gmail: str, client_key: str) -> None:
        key = self._rate_key(gmail, client_key)
        now = time.time()
        recent = [item for item in _LOGIN_FAILURES.get(key, []) if item >= now - 900]
        _LOGIN_FAILURES[key] = recent
        if len(recent) >= 5:
            raise RateLimitError("Demasiados intentos. Espera unos minutos antes de volver a intentarlo.")

    def _record_failure(self, gmail: str, client_key: str) -> None:
        key = self._rate_key(gmail, client_key)
        _LOGIN_FAILURES.setdefault(key, []).append(time.time())

    def _clear_failures(self, gmail: str, client_key: str) -> None:
        _LOGIN_FAILURES.pop(self._rate_key(gmail, client_key), None)
