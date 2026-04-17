from __future__ import annotations

from datetime import date

from backend.app.domain.models import Pick, PlayerProp
from backend.app.repositories.contracts import PickRepository
from backend.app.repositories.postgres.base import PostgresRepository


class PostgresPickRepository(PostgresRepository, PickRepository):
    def list_picks_for_day(self, target_date: date) -> list[Pick]:
        query = """
        SELECT id, match_id, market, selection, probability, fair_odds, offered_odds, edge, stake_fraction, provider, created_at
        FROM picks
        WHERE DATE(created_at) = %s
        ORDER BY created_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (target_date,))
                rows = cursor.fetchall()
        return [Pick(*row) for row in rows]

    def list_picks_for_match(self, match_id: str) -> list[Pick]:
        query = """
        SELECT id, match_id, market, selection, probability, fair_odds, offered_odds, edge, stake_fraction, provider, created_at
        FROM picks
        WHERE match_id = %s
        ORDER BY created_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (match_id,))
                rows = cursor.fetchall()
        return [Pick(*row) for row in rows]

    def get_pick(self, pick_id: str) -> Pick | None:
        query = """
        SELECT id, match_id, market, selection, probability, fair_odds, offered_odds, edge, stake_fraction, provider, created_at
        FROM picks
        WHERE id = %s
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (pick_id,))
                row = cursor.fetchone()
        return Pick(*row) if row else None

    def save_pick(self, pick: Pick) -> None:
        query = """
        INSERT INTO picks (id, match_id, market, selection, probability, fair_odds, offered_odds, edge, stake_fraction, provider, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            probability = EXCLUDED.probability,
            fair_odds = EXCLUDED.fair_odds,
            offered_odds = EXCLUDED.offered_odds,
            edge = EXCLUDED.edge,
            stake_fraction = EXCLUDED.stake_fraction,
            provider = EXCLUDED.provider
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    query,
                    (pick.id, pick.match_id, pick.market, pick.selection, pick.probability, pick.fair_odds, pick.offered_odds, pick.edge, pick.stake_fraction, pick.provider, pick.created_at),
                )
            conn.commit()

    def save_player_props(self, props: list[PlayerProp]) -> None:
        query = """
        INSERT INTO player_props (id, match_id, player_id, player_name, metric, line, probability, expected_value, confidence_label, generated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            probability = EXCLUDED.probability,
            expected_value = EXCLUDED.expected_value,
            confidence_label = EXCLUDED.confidence_label,
            generated_at = EXCLUDED.generated_at
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(
                    query,
                    [(item.id, item.match_id, item.player_id, item.player_name, item.metric, item.line, item.probability, item.expected_value, item.confidence_label, item.generated_at) for item in props],
                )
            conn.commit()
