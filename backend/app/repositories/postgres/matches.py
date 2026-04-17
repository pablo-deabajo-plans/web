from __future__ import annotations

from datetime import date

import psycopg2

from backend.app.core.logging import get_logger
from backend.app.domain.models import Match
from backend.app.repositories.contracts import MatchRepository
from backend.app.repositories.postgres.base import PostgresRepository


LOGGER = get_logger(__name__)

LIST_MATCHES_FOR_DAY_QUERY = """
SELECT id, competition, kickoff_at, home_team, away_team, status, source
FROM matches
WHERE DATE(kickoff_at) = %s
ORDER BY kickoff_at ASC
"""

GET_MATCH_QUERY = """
SELECT id, competition, kickoff_at, home_team, away_team, status, source
FROM matches
WHERE id = %s
"""

UPSERT_MATCHES_QUERY = """
INSERT INTO matches (id, competition, kickoff_at, home_team, away_team, status, source)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    competition = EXCLUDED.competition,
    kickoff_at = EXCLUDED.kickoff_at,
    home_team = EXCLUDED.home_team,
    away_team = EXCLUDED.away_team,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    updated_at = NOW()
"""


class PostgresMatchRepositoryError(RuntimeError):
    """Raised when the match repository cannot complete a PostgreSQL operation."""


class PostgresMatchRepository(PostgresRepository, MatchRepository):
    def list_matches_for_day(self, target_date: date) -> list[Match]:
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(LIST_MATCHES_FOR_DAY_QUERY, (target_date,))
                    rows = cursor.fetchall()
        except psycopg2.Error as exc:
            LOGGER.exception("Failed to list matches for day target_date=%s", target_date)
            raise PostgresMatchRepositoryError("Could not fetch matches for the requested date") from exc
        return [self._row_to_match(row) for row in rows]

    def get_match(self, match_id: str) -> Match | None:
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(GET_MATCH_QUERY, (match_id,))
                    row = cursor.fetchone()
        except psycopg2.Error as exc:
            LOGGER.exception("Failed to fetch match match_id=%s", match_id)
            raise PostgresMatchRepositoryError("Could not fetch the requested match") from exc
        return self._row_to_match(row) if row else None

    def upsert_matches(self, matches: list[Match]) -> None:
        if not matches:
            return

        payload = [
            (
                item.id,
                item.competition,
                item.kickoff_at,
                item.home_team,
                item.away_team,
                item.status,
                item.source,
            )
            for item in matches
        ]

        conn = self._connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.executemany(UPSERT_MATCHES_QUERY, payload)
        except psycopg2.Error as exc:
            conn.rollback()
            LOGGER.exception("Failed to upsert matches count=%s", len(matches))
            raise PostgresMatchRepositoryError("Could not persist matches") from exc
        finally:
            conn.close()

    @staticmethod
    def _row_to_match(row: tuple) -> Match:
        return Match(
            id=row[0],
            competition=row[1],
            kickoff_at=row[2],
            home_team=row[3],
            away_team=row[4],
            status=row[5],
            source=row[6],
        )
