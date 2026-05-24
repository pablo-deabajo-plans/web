from __future__ import annotations

import base64
from dataclasses import dataclass, field as dataclasses_field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from uuid import uuid4

import bcrypt

from backend.app.domain.models import User
from backend.app.repositories.contracts import LoginAttemptRepository, UserRepository


class _InMemoryLoginAttemptStore:
    """Default in-process fallback. Use PostgresLoginAttemptRepository in production."""

    def __init__(self) -> None:
        self._data: dict[str, list[float]] = {}

    def get_recent_failures(self, key: str, window_seconds: int) -> int:
        cutoff = time.time() - window_seconds
        recent = [ts for ts in self._data.get(key, []) if ts >= cutoff]
        self._data[key] = recent
        return len(recent)

    def record_failure(self, key: str) -> None:
        self._data.setdefault(key, []).append(time.time())

    def clear_failures(self, key: str) -> None:
        self._data.pop(key, None)


class AuthError(ValueError):
    pass


class RateLimitError(AuthError):
    pass


_LOGGER = logging.getLogger(__name__)
_VERIFICATION_TOKEN_TTL_SECONDS = 60 * 60 * 24  # 24 hours
_RESET_TOKEN_TTL_SECONDS = 60 * 60  # 1 hour


@dataclass(frozen=True)
class SessionData:
    user_id: str
    expires_at: datetime
    csrf_token: str
    issued_at: datetime = dataclasses_field(default_factory=lambda: datetime.now(timezone.utc))


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
    def __init__(
        self,
        users: UserRepository,
        session_secret: str,
        session_ttl_seconds: int,
        login_attempts: LoginAttemptRepository | None = None,
    ) -> None:
        self._users = users
        self._session_secret = session_secret
        self._session_ttl_seconds = session_ttl_seconds
        self._login_attempts: LoginAttemptRepository = login_attempts or _InMemoryLoginAttemptStore()

    def register(self, gmail: str, nombre: str, password: str, client_key: str = "") -> User:
        self._check_rate_limit("__register__", client_key)
        try:
            gmail = validate_gmail(gmail)
            nombre = validate_nombre(nombre)
            password = validate_password(password)
        except AuthError:
            self._record_failure("__register__", client_key)
            raise
        if self._users.get_by_gmail(gmail) is not None:
            self._record_failure("__register__", client_key)
            raise AuthError("Ya existe una cuenta con ese correo.")
        user = User(
            id=str(uuid4()),
            gmail=gmail,
            nombre=nombre,
            password_hash=hash_password(password),
            plan="free",
        )
        self._users.create_user(user)
        token = self.generate_verification_token(user.id)
        _LOGGER.info("Email verification token generated user_id=%s token=%s", user.id, token)
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
        updated = self._users.update_password_hash(user.id, hash_password(validate_password(new_password)))
        self._users.update_password_changed_at(user.id)
        return updated

    def generate_verification_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_VERIFICATION_TOKEN_TTL_SECONDS)
        self._users.create_verification_token(user_id, token, expires_at)
        return token

    def find_user_by_gmail(self, gmail: str) -> User | None:
        return self._users.get_by_gmail(normalize_gmail(gmail))

    def generate_password_reset_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_RESET_TOKEN_TTL_SECONDS)
        self._users.create_reset_token(user_id, token, expires_at)
        return token

    def get_user_by_reset_token(self, token: str) -> User | None:
        return self._users.get_by_reset_token(token)

    def reset_password(self, token: str, new_password: str) -> User:
        user = self._users.get_by_reset_token(token)
        if user is None:
            raise AuthError("El enlace de restablecimiento ha caducado o no es válido.")
        updated = self._users.update_password_hash(user.id, hash_password(validate_password(new_password)))
        self._users.update_password_changed_at(user.id)
        self._users.delete_reset_token(user.id)
        return updated

    def verify_email_token(self, token: str) -> User | None:
        user = self._users.get_by_verification_token(token)
        if user is None:
            return None
        if user.email_verified_at is not None:
            return user
        return self._users.verify_email(user.id, datetime.now(timezone.utc))

    def create_session_token(self, user: User) -> str:
        now = datetime.now(timezone.utc)
        jti = str(uuid4())
        payload = {
            "sub": user.id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._session_ttl_seconds)).timestamp()),
            "csrf": secrets.token_urlsafe(24),
            "jti": jti,
        }
        expires_at = now + timedelta(seconds=self._session_ttl_seconds)
        self._users.create_session(jti, user.id, str(payload["csrf"]), expires_at)
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
        jti = payload.get("jti")
        if jti is not None and not self._users.session_exists(jti):
            return None
        iat = payload.get("iat")
        issued_at = datetime.fromtimestamp(int(iat), tz=timezone.utc) if iat is not None else datetime.fromtimestamp(0, tz=timezone.utc)
        return SessionData(user_id=str(payload["sub"]), expires_at=expires_at, csrf_token=str(payload["csrf"]), issued_at=issued_at)

    def current_user(self, token: str | None) -> User | None:
        session = self.read_session(token)
        if session is None:
            return None
        user = self._users.get_by_id(session.user_id)
        if user is None:
            return None
        if user.password_changed_at is not None and session.issued_at < user.password_changed_at:
            return None
        return user

    def revoke_session(self, token: str | None) -> None:
        if not token:
            return
        payload = self._read_payload(token)
        if payload is None:
            return
        jti = payload.get("jti")
        if jti:
            self._users.delete_session(jti)

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
        if self._login_attempts.get_recent_failures(key, 900) >= 5:
            raise RateLimitError("Demasiados intentos. Espera unos minutos antes de volver a intentarlo.")

    def _record_failure(self, gmail: str, client_key: str) -> None:
        self._login_attempts.record_failure(self._rate_key(gmail, client_key))

    def _clear_failures(self, gmail: str, client_key: str) -> None:
        self._login_attempts.clear_failures(self._rate_key(gmail, client_key))
