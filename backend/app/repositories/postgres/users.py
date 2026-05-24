from __future__ import annotations

from datetime import datetime, timezone

from backend.app.domain.models import User

_SELECT = "SELECT id, gmail, nombre, password_hash, plan, password_changed_at, email_verified_at FROM users"


class PostgresUserRepository:
    def __init__(self, connection_factory) -> None:
        self._connection_factory = connection_factory

    def get_by_id(self, user_id: str) -> User | None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"{_SELECT} WHERE id = %s", (user_id,))
                row = cursor.fetchone()
        return self._row_to_user(row)

    def get_by_gmail(self, gmail: str) -> User | None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"{_SELECT} WHERE lower(gmail) = lower(%s)", (gmail,))
                row = cursor.fetchone()
        return self._row_to_user(row)

    def create_user(self, user: User) -> None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (id, gmail, nombre, password_hash, plan) VALUES (%s, %s, %s, %s, %s)",
                    (user.id, user.gmail, user.nombre, user.password_hash, user.plan),
                )
            conn.commit()

    def update_nombre(self, user_id: str, nombre: str) -> User:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE users SET nombre = %s WHERE id = %s RETURNING id, gmail, nombre, password_hash, plan, password_changed_at, email_verified_at",
                    (nombre, user_id),
                )
                row = cursor.fetchone()
            conn.commit()
        if row is None:
            raise ValueError("user not found")
        return self._row_to_user(row)

    def update_password_hash(self, user_id: str, password_hash: str) -> User:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s RETURNING id, gmail, nombre, password_hash, plan, password_changed_at, email_verified_at",
                    (password_hash, user_id),
                )
                row = cursor.fetchone()
            conn.commit()
        if row is None:
            raise ValueError("user not found")
        return self._row_to_user(row)

    def update_password_changed_at(self, user_id: str) -> None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password_changed_at = NOW() WHERE id = %s",
                    (user_id,),
                )
            conn.commit()

    def create_verification_token(self, user_id: str, token: str, expires_at: datetime) -> None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO email_verification_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET token = EXCLUDED.token, expires_at = EXCLUDED.expires_at
                    """,
                    (user_id, token, expires_at),
                )
            conn.commit()

    def get_by_verification_token(self, token: str) -> User | None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT u.id, u.gmail, u.nombre, u.password_hash, u.plan, u.password_changed_at, u.email_verified_at
                    FROM users u
                    JOIN email_verification_tokens t ON t.user_id = u.id
                    WHERE t.token = %s AND t.expires_at > NOW()
                    """,
                    (token,),
                )
                row = cursor.fetchone()
        return self._row_to_user(row)

    def verify_email(self, user_id: str, verified_at: datetime) -> User:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET email_verified_at = %s WHERE id = %s RETURNING id, gmail, nombre, password_hash, plan, password_changed_at, email_verified_at",
                    (verified_at, user_id),
                )
                row = cursor.fetchone()
                cursor.execute("DELETE FROM email_verification_tokens WHERE user_id = %s", (user_id,))
            conn.commit()
        if row is None:
            raise ValueError("user not found")
        return self._row_to_user(row)

    def create_session(self, session_id: str, user_id: str, csrf_token: str, expires_at: datetime) -> None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO app.user_sessions (id, user_id, csrf_token, expires_at) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (session_id, user_id, csrf_token, expires_at),
                )
            conn.commit()

    def session_exists(self, session_id: str) -> bool:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM app.user_sessions WHERE id = %s AND expires_at > NOW()",
                    (session_id,),
                )
                return cursor.fetchone() is not None

    def delete_session(self, session_id: str) -> None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM app.user_sessions WHERE id = %s", (session_id,))
            conn.commit()

    def create_reset_token(self, user_id: str, token: str, expires_at) -> None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET token = EXCLUDED.token, expires_at = EXCLUDED.expires_at
                    """,
                    (user_id, token, expires_at),
                )
            conn.commit()

    def get_by_reset_token(self, token: str) -> User | None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT u.id, u.gmail, u.nombre, u.password_hash, u.plan, u.password_changed_at, u.email_verified_at
                    FROM users u
                    JOIN password_reset_tokens t ON t.user_id = u.id
                    WHERE t.token = %s AND t.expires_at > NOW()
                    """,
                    (token,),
                )
                row = cursor.fetchone()
        return self._row_to_user(row)

    def delete_reset_token(self, user_id: str) -> None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM password_reset_tokens WHERE user_id = %s", (user_id,))
            conn.commit()

    @staticmethod
    def _row_to_user(row) -> User | None:
        if row is None:
            return None
        return User(
            id=str(row[0]),
            gmail=str(row[1]),
            nombre=str(row[2]),
            password_hash=str(row[3]),
            plan=str(row[4]),
            password_changed_at=row[5],
            email_verified_at=row[6],
        )
