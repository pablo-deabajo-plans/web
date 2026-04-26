from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from backend.app.core.cache import TTLCache


MONEY_PRECISION = Decimal("0.0001")


@dataclass(frozen=True)
class ROIQuery:
    start_date: date
    end_date: date
    league: str | None = None
    market: str | None = None


@dataclass(frozen=True)
class ROIResult:
    total_bets: int
    total_stake: float
    total_profit: float
    roi: float | None
    wins: int
    losses: int
    pushes: int


@dataclass(frozen=True)
class ROIGroupResult:
    key: str
    metrics: ROIResult


BASE_ROI_QUERY = """
SELECT
    COUNT(*) AS total_bets,
    COALESCE(SUM(r.stake_units), 0) AS total_stake,
    COALESCE(SUM(r.profit_units), 0) AS total_profit,
    SUM(CASE WHEN LOWER(COALESCE(r.status, '')) = 'won' THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN LOWER(COALESCE(r.status, '')) = 'lost' THEN 1 ELSE 0 END) AS losses,
    SUM(CASE WHEN LOWER(COALESCE(r.status, '')) = 'push' THEN 1 ELSE 0 END) AS pushes
FROM results r
JOIN picks p ON p.id = r.pick_id
JOIN matches m ON m.id = p.match_id
WHERE (r.settled_at AT TIME ZONE 'UTC')::date >= %s
  AND (r.settled_at AT TIME ZONE 'UTC')::date <= %s
"""


class ROIService:
    def __init__(
        self,
        connection_factory,
        cache: TTLCache | None = None,
        ttl_seconds: int = 0,
    ) -> None:
        self._connection_factory = connection_factory
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    def calculate(self, query: ROIQuery) -> ROIResult:
        self._validate_query(query)

        def _load() -> ROIResult:
            sql, params = self._build_aggregate_query(query)
            row = self._fetch_one(sql, params)
            return self._row_to_result(row)

        if self._cache is None or self._ttl_seconds <= 0:
            return _load()
        return self._cache.get_or_set("roi", self._cache_key(query), self._ttl_seconds, _load)

    def group_by_league(self, query: ROIQuery) -> list[ROIGroupResult]:
        self._validate_query(query)
        sql, params = self._build_group_query(query, group_sql="m.competition", order_sql="m.competition")
        rows = self._fetch_all(sql, params)
        return [ROIGroupResult(key=str(row[0]), metrics=self._row_to_result(row[1:])) for row in rows]

    def group_by_market(self, query: ROIQuery) -> list[ROIGroupResult]:
        self._validate_query(query)
        sql, params = self._build_group_query(query, group_sql="p.market", order_sql="p.market")
        rows = self._fetch_all(sql, params)
        return [ROIGroupResult(key=str(row[0]), metrics=self._row_to_result(row[1:])) for row in rows]

    def _build_aggregate_query(self, query: ROIQuery) -> tuple[str, list[object]]:
        filters, params = self._filters(query)
        sql = BASE_ROI_QUERY + filters
        return sql, params

    def _build_group_query(self, query: ROIQuery, *, group_sql: str, order_sql: str) -> tuple[str, list[object]]:
        filters, params = self._filters(query)
        sql = (
            f"SELECT {group_sql} AS group_key, "
            "COUNT(*) AS total_bets, "
            "COALESCE(SUM(r.stake_units), 0) AS total_stake, "
            "COALESCE(SUM(r.profit_units), 0) AS total_profit, "
            "SUM(CASE WHEN LOWER(COALESCE(r.status, '')) = 'won' THEN 1 ELSE 0 END) AS wins, "
            "SUM(CASE WHEN LOWER(COALESCE(r.status, '')) = 'lost' THEN 1 ELSE 0 END) AS losses, "
            "SUM(CASE WHEN LOWER(COALESCE(r.status, '')) = 'push' THEN 1 ELSE 0 END) AS pushes "
            "FROM results r "
            "JOIN picks p ON p.id = r.pick_id "
            "JOIN matches m ON m.id = p.match_id "
            "WHERE (r.settled_at AT TIME ZONE 'UTC')::date >= %s "
            "AND (r.settled_at AT TIME ZONE 'UTC')::date <= %s "
            f"{filters} "
            f"GROUP BY {group_sql} "
            f"ORDER BY {order_sql} ASC"
        )
        return sql, params

    @staticmethod
    def _filters(query: ROIQuery) -> tuple[str, list[object]]:
        extra_filters: list[str] = []
        params: list[object] = [query.start_date, query.end_date]
        if query.league is not None:
            extra_filters.append("AND m.competition = %s")
            params.append(query.league)
        if query.market is not None:
            extra_filters.append("AND p.market = %s")
            params.append(query.market)
        return " " + " ".join(extra_filters) if extra_filters else "", params

    def _fetch_one(self, query: str, params: list[object]):
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()

    def _fetch_all(self, query: str, params: list[object]):
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()

    @staticmethod
    def _validate_query(query: ROIQuery) -> None:
        if query.end_date < query.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")

    @staticmethod
    def _row_to_result(row) -> ROIResult:
        total_bets = int(row[0] or 0)
        total_stake = Decimal(str(row[1] or 0))
        total_profit = Decimal(str(row[2] or 0))
        wins = int(row[3] or 0)
        losses = int(row[4] or 0)
        pushes = int(row[5] or 0)

        roi = None
        if total_stake != Decimal("0"):
            roi = float((total_profit / total_stake).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP))

        return ROIResult(
            total_bets=total_bets,
            total_stake=float(total_stake.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)),
            total_profit=float(total_profit.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)),
            roi=roi,
            wins=wins,
            losses=losses,
            pushes=pushes,
        )

    @staticmethod
    def _cache_key(query: ROIQuery) -> str:
        return "|".join(
            [
                query.start_date.isoformat(),
                query.end_date.isoformat(),
                query.league or "*",
                query.market or "*",
            ]
        )
