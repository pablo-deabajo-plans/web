from __future__ import annotations

from datetime import date

from backend.app.domain.models import Pick, PlayerProp
from backend.app.repositories.contracts import PickRepository
from backend.app.repositories.postgres.base import PostgresRepository


class PostgresPickRepository(PostgresRepository, PickRepository):
    def list_picks_for_day(self, target_date: date) -> list[Pick]:
        query = """
        SELECT
            id,
            match_id,
            market,
            selection,
            probability,
            fair_odds,
            offered_odds,
            edge,
            stake_fraction,
            stake_units,
            closing_odds,
            clv_absolute,
            clv_percent,
            status,
            provider,
            analysis_id,
            created_at
        FROM picks
        WHERE (created_at AT TIME ZONE 'UTC')::date = %s
        ORDER BY created_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (target_date,))
                rows = cursor.fetchall()
        return [self._row_to_pick(row) for row in rows]

    def list_picks_for_match(self, match_id: str) -> list[Pick]:
        query = """
        SELECT
            id,
            match_id,
            market,
            selection,
            probability,
            fair_odds,
            offered_odds,
            edge,
            stake_fraction,
            stake_units,
            closing_odds,
            clv_absolute,
            clv_percent,
            status,
            provider,
            analysis_id,
            created_at
        FROM picks
        WHERE match_id = %s
        ORDER BY created_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (match_id,))
                rows = cursor.fetchall()
        return [self._row_to_pick(row) for row in rows]

    def get_pick(self, pick_id: str) -> Pick | None:
        query = """
        SELECT
            id,
            match_id,
            market,
            selection,
            probability,
            fair_odds,
            offered_odds,
            edge,
            stake_fraction,
            stake_units,
            closing_odds,
            clv_absolute,
            clv_percent,
            status,
            provider,
            analysis_id,
            created_at
        FROM picks
        WHERE id = %s
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (pick_id,))
                row = cursor.fetchone()
        return self._row_to_pick(row) if row else None

    def save_pick(self, pick: Pick) -> None:
        query = """
        INSERT INTO picks (
            id,
            match_id,
            analysis_id,
            market,
            selection,
            probability,
            fair_odds,
            offered_odds,
            edge,
            stake_fraction,
            stake_units,
            closing_odds,
            clv_absolute,
            clv_percent,
            provider,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            analysis_id = EXCLUDED.analysis_id,
            probability = EXCLUDED.probability,
            fair_odds = EXCLUDED.fair_odds,
            offered_odds = EXCLUDED.offered_odds,
            edge = EXCLUDED.edge,
            stake_fraction = EXCLUDED.stake_fraction,
            stake_units = EXCLUDED.stake_units,
            closing_odds = EXCLUDED.closing_odds,
            clv_absolute = EXCLUDED.clv_absolute,
            clv_percent = EXCLUDED.clv_percent,
            provider = EXCLUDED.provider,
            status = EXCLUDED.status
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        pick.id,
                        pick.match_id,
                        pick.analysis_id,
                        pick.market,
                        pick.selection,
                        pick.probability,
                        pick.fair_odds,
                        pick.offered_odds,
                        pick.edge,
                        pick.stake_fraction,
                        pick.stake_units,
                        pick.closing_odds,
                        pick.clv_absolute,
                        pick.clv_percent,
                        pick.provider,
                        pick.status,
                        pick.created_at,
                    ),
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

    @staticmethod
    def _row_to_pick(row: tuple) -> Pick:
        return Pick(
            id=row[0],
            match_id=row[1],
            market=row[2],
            selection=row[3],
            probability=float(row[4]),
            fair_odds=float(row[5]),
            offered_odds=float(row[6]),
            edge=float(row[7]),
            stake_fraction=float(row[8]),
            stake_units=float(row[9]) if row[9] is not None else None,
            closing_odds=float(row[10]) if row[10] is not None else None,
            clv_absolute=float(row[11]) if row[11] is not None else None,
            clv_percent=float(row[12]) if row[12] is not None else None,
            status=row[13],
            provider=row[14],
            analysis_id=str(row[15]) if row[15] is not None else None,
            created_at=row[16],
        )
