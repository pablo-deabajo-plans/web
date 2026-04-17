from __future__ import annotations

from datetime import date

from backend.app.domain.models import Match
from backend.app.repositories.contracts import MatchRepository
from backend.app.repositories.postgres.base import PostgresRepository


class PostgresMatchRepository(PostgresRepository, MatchRepository):
    def list_matches_for_day(self, target_date: date) -> list[Match]:
        query = """
        SELECT id, competition, kickoff_at, home_team, away_team, status, source
        FROM matches
        WHERE DATE(kickoff_at) = %s
        ORDER BY kickoff_at ASC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (target_date,))
                rows = cursor.fetchall()
        return [Match(*row) for row in rows]

    def get_match(self, match_id: str) -> Match | None:
        query = """
        SELECT id, competition, kickoff_at, home_team, away_team, status, source
        FROM matches
        WHERE id = %s
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (match_id,))
                row = cursor.fetchone()
        return Match(*row) if row else None

    def upsert_matches(self, matches: list[Match]) -> None:
        query = """
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
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(
                    query,
                    [(item.id, item.competition, item.kickoff_at, item.home_team, item.away_team, item.status, item.source) for item in matches],
                )
            conn.commit()
