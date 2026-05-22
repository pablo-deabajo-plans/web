from __future__ import annotations

from datetime import date
from typing import Sequence

import psycopg2
from psycopg2.extras import Json

from backend.app.core.logging import get_logger
from backend.app.domain.models import Match
from backend.app.repositories.contracts import MatchRepository
from backend.app.repositories.postgres.base import PostgresRepository


LOGGER = get_logger(__name__)

LIST_MATCHES_FOR_DAY_QUERY = """
SELECT
    id,
    external_id,
    competition,
    kickoff_at,
    home_team,
    away_team,
    status,
    source,
    home_score,
    away_score,
    home_corners,
    away_corners,
    home_shots,
    away_shots,
    home_shots_on_target,
    away_shots_on_target,
    created_at,
    updated_at
FROM matches
WHERE (kickoff_at AT TIME ZONE 'UTC')::date = %s
ORDER BY kickoff_at ASC
"""

GET_MATCH_QUERY = """
SELECT
    id,
    external_id,
    competition,
    kickoff_at,
    home_team,
    away_team,
    status,
    source,
    home_score,
    away_score,
    home_corners,
    away_corners,
    home_shots,
    away_shots,
    home_shots_on_target,
    away_shots_on_target,
    created_at,
    updated_at
FROM matches
WHERE id = %s
"""

LIST_FINISHED_MATCHES_QUERY = """
SELECT
    id,
    external_id,
    competition,
    kickoff_at,
    home_team,
    away_team,
    status,
    source,
    home_score,
    away_score,
    home_corners,
    away_corners,
    home_shots,
    away_shots,
    home_shots_on_target,
    away_shots_on_target,
    created_at,
    updated_at
FROM matches
WHERE competition = %s
  AND (kickoff_at AT TIME ZONE 'UTC')::date < %s
  AND LOWER(COALESCE(status, '')) = 'finished'
  AND home_score IS NOT NULL
  AND away_score IS NOT NULL
  AND (
      %s::jsonb IS NULL
      OR home_team IN (SELECT jsonb_array_elements_text(%s::jsonb))
      OR away_team IN (SELECT jsonb_array_elements_text(%s::jsonb))
  )
ORDER BY kickoff_at DESC
"""

UPSERT_MATCHES_QUERY = """
INSERT INTO matches (
    id,
    external_id,
    competition,
    kickoff_at,
    home_team,
    away_team,
    status,
    source,
    home_score,
    away_score,
    home_corners,
    away_corners,
    home_shots,
    away_shots,
    home_shots_on_target,
    away_shots_on_target
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    external_id = EXCLUDED.external_id,
    competition = EXCLUDED.competition,
    kickoff_at = EXCLUDED.kickoff_at,
    home_team = EXCLUDED.home_team,
    away_team = EXCLUDED.away_team,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    home_score = EXCLUDED.home_score,
    away_score = EXCLUDED.away_score,
    home_corners = EXCLUDED.home_corners,
    away_corners = EXCLUDED.away_corners,
    home_shots = EXCLUDED.home_shots,
    away_shots = EXCLUDED.away_shots,
    home_shots_on_target = EXCLUDED.home_shots_on_target,
    away_shots_on_target = EXCLUDED.away_shots_on_target,
    updated_at = NOW()
"""

UPSERT_SPORTS_MATCHES_QUERY = """
INSERT INTO sports.matches (
    id,
    provider,
    external_id,
    competition,
    kickoff_at,
    home_team,
    away_team,
    status,
    home_score,
    away_score
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    provider = EXCLUDED.provider,
    external_id = EXCLUDED.external_id,
    competition = EXCLUDED.competition,
    kickoff_at = EXCLUDED.kickoff_at,
    home_team = EXCLUDED.home_team,
    away_team = EXCLUDED.away_team,
    status = EXCLUDED.status,
    home_score = EXCLUDED.home_score,
    away_score = EXCLUDED.away_score,
    updated_at = NOW()
"""

UPSERT_SPORTS_TEAM_MATCH_STATS_QUERY = """
INSERT INTO sports.team_match_stats (
    id,
    match_id,
    side,
    goals,
    shots,
    shots_on_target,
    corners,
    source,
    captured_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (id) DO UPDATE SET
    goals = EXCLUDED.goals,
    shots = EXCLUDED.shots,
    shots_on_target = EXCLUDED.shots_on_target,
    corners = EXCLUDED.corners,
    source = EXCLUDED.source,
    captured_at = EXCLUDED.captured_at
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

    def list_finished_matches(
        self,
        competition: str,
        before_date: date,
        teams: Sequence[str] | None = None,
    ) -> list[Match]:
        team_filter = Json(list(teams)) if teams else None
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        LIST_FINISHED_MATCHES_QUERY,
                        (competition, before_date, team_filter, team_filter, team_filter),
                    )
                    rows = cursor.fetchall()
        except psycopg2.Error as exc:
            LOGGER.exception(
                "Failed to list finished matches competition=%s before_date=%s teams=%s",
                competition,
                before_date,
                len(teams or []),
            )
            raise PostgresMatchRepositoryError("Could not fetch finished historical matches") from exc
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
                item.external_id,
                item.competition,
                item.kickoff_at,
                item.home_team,
                item.away_team,
                item.status,
                item.source,
                item.home_score,
                item.away_score,
                item.home_corners,
                item.away_corners,
                item.home_shots,
                item.away_shots,
                item.home_shots_on_target,
                item.away_shots_on_target,
            )
            for item in matches
        ]

        conn = self._connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.executemany(UPSERT_MATCHES_QUERY, payload)
                    cursor.executemany(UPSERT_SPORTS_MATCHES_QUERY, self._sports_match_payload(matches))
                    cursor.executemany(UPSERT_SPORTS_TEAM_MATCH_STATS_QUERY, self._sports_team_stats_payload(matches))
        except psycopg2.Error as exc:
            conn.rollback()
            LOGGER.exception("Failed to upsert matches count=%s", len(matches))
            raise PostgresMatchRepositoryError("Could not persist matches") from exc
        finally:
            conn.close()

    @staticmethod
    def _provider_for_match(match: Match) -> str:
        return str(match.source or "internal").strip() or "internal"

    @classmethod
    def _sports_match_payload(cls, matches: list[Match]) -> list[tuple]:
        return [
            (
                item.id,
                cls._provider_for_match(item),
                item.external_id,
                item.competition,
                item.kickoff_at,
                item.home_team,
                item.away_team,
                item.status,
                item.home_score,
                item.away_score,
            )
            for item in matches
        ]

    @classmethod
    def _sports_team_stats_payload(cls, matches: list[Match]) -> list[tuple]:
        payload = []
        for item in matches:
            source = cls._provider_for_match(item)
            payload.extend(
                [
                    (
                        f"{item.id}:home:latest",
                        item.id,
                        "home",
                        item.home_score,
                        item.home_shots,
                        item.home_shots_on_target,
                        item.home_corners,
                        source,
                    ),
                    (
                        f"{item.id}:away:latest",
                        item.id,
                        "away",
                        item.away_score,
                        item.away_shots,
                        item.away_shots_on_target,
                        item.away_corners,
                        source,
                    ),
                ]
            )
        return payload

    @staticmethod
    def _row_to_match(row: tuple) -> Match:
        return Match(
            id=row[0],
            external_id=row[1],
            competition=row[2],
            kickoff_at=row[3],
            home_team=row[4],
            away_team=row[5],
            status=row[6],
            source=row[7],
            home_score=row[8],
            away_score=row[9],
            home_corners=float(row[10]) if row[10] is not None else None,
            away_corners=float(row[11]) if row[11] is not None else None,
            home_shots=float(row[12]) if row[12] is not None else None,
            away_shots=float(row[13]) if row[13] is not None else None,
            home_shots_on_target=float(row[14]) if row[14] is not None else None,
            away_shots_on_target=float(row[15]) if row[15] is not None else None,
            created_at=row[16],
            updated_at=row[17],
        )
