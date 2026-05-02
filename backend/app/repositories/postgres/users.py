from __future__ import annotations

from backend.app.domain.models import User


class PostgresUserRepository:
    def __init__(self, connection_factory) -> None:
        self._connection_factory = connection_factory

    def get_by_id(self, user_id: str) -> User | None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, gmail, nombre, password_hash, plan FROM users WHERE id = %s",
                    (user_id,),
                )
                row = cursor.fetchone()
        return self._row_to_user(row)

    def get_by_gmail(self, gmail: str) -> User | None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, gmail, nombre, password_hash, plan FROM users WHERE lower(gmail) = lower(%s)",
                    (gmail,),
                )
                row = cursor.fetchone()
        return self._row_to_user(row)

    def create_user(self, user: User) -> None:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (id, gmail, nombre, password_hash, plan)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user.id, user.gmail, user.nombre, user.password_hash, user.plan),
                )
            conn.commit()

    def update_nombre(self, user_id: str, nombre: str) -> User:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE users
                    SET nombre = %s
                    WHERE id = %s
                    RETURNING id, gmail, nombre, password_hash, plan
                    """,
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
                    """
                    UPDATE users
                    SET password_hash = %s
                    WHERE id = %s
                    RETURNING id, gmail, nombre, password_hash, plan
                    """,
                    (password_hash, user_id),
                )
                row = cursor.fetchone()
            conn.commit()
        if row is None:
            raise ValueError("user not found")
        return self._row_to_user(row)

    @staticmethod
    def _row_to_user(row) -> User | None:
        if row is None:
            return None
        return User(id=str(row[0]), gmail=str(row[1]), nombre=str(row[2]), password_hash=str(row[3]), plan=str(row[4]))
