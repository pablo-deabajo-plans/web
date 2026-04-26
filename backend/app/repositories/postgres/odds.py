from __future__ import annotations

from datetime import date

from backend.app.domain.models import OddsQuote
from backend.app.repositories.contracts import OddsRepository
from backend.app.repositories.postgres.base import PostgresRepository


class PostgresOddsRepository(PostgresRepository, OddsRepository):
    def list_latest_odds_for_day(self, target_date: date) -> list[OddsQuote]:
        query = """
        SELECT id, match_id, market, selection, decimal_odds, sportsbook, captured_at
        FROM odds
        WHERE (captured_at AT TIME ZONE 'UTC')::date = %s
        ORDER BY captured_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (target_date,))
                rows = cursor.fetchall()
        return [
            OddsQuote(
                match_id=row[1],
                market=row[2],
                selection=row[3],
                decimal_odds=row[4],
                sportsbook=row[5],
                captured_at=row[6],
                id=row[0],
            )
            for row in rows
        ]

    def list_odds_for_match(self, match_id: str) -> list[OddsQuote]:
        query = """
        SELECT id, match_id, market, selection, decimal_odds, sportsbook, captured_at
        FROM odds
        WHERE match_id = %s
        ORDER BY captured_at DESC
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (match_id,))
                rows = cursor.fetchall()
        return [
            OddsQuote(
                match_id=row[1],
                market=row[2],
                selection=row[3],
                decimal_odds=row[4],
                sportsbook=row[5],
                captured_at=row[6],
                id=row[0],
            )
            for row in rows
        ]

    def upsert_odds(self, quotes: list[OddsQuote]) -> None:
        query = """
        INSERT INTO odds (id, match_id, market, selection, sportsbook, decimal_odds, captured_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            market = EXCLUDED.market,
            selection = EXCLUDED.selection,
            sportsbook = EXCLUDED.sportsbook,
            decimal_odds = EXCLUDED.decimal_odds,
            captured_at = EXCLUDED.captured_at
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(
                    query,
                    [(item.id, item.match_id, item.market, item.selection, item.sportsbook, item.decimal_odds, item.captured_at) for item in quotes],
                )
            conn.commit()
