from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from backend.app.core.cache import TTLCache
from backend.app.domain.models import Match, Pick, Result
from backend.app.repositories.contracts import MatchRepository, PickRepository, ResultRepository


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
class ROIItem:
    match: Match
    pick: Pick
    result: Result


@dataclass(frozen=True)
class ROIGroupResult:
    key: str
    metrics: ROIResult


class ROIService:
    def __init__(
        self,
        matches: MatchRepository,
        picks: PickRepository,
        results: ResultRepository,
        cache: TTLCache | None = None,
        ttl_seconds: int = 0,
    ) -> None:
        self._matches = matches
        self._picks = picks
        self._results = results
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    def calculate(self, query: ROIQuery) -> ROIResult:
        self._validate_query(query)

        def _load() -> ROIResult:
            return self._summarize(self._load_items(query))

        if self._cache is None or self._ttl_seconds <= 0:
            return _load()
        return self._cache.get_or_set("roi", self._cache_key(query), self._ttl_seconds, _load)

    def group_by_league(self, query: ROIQuery) -> list[ROIGroupResult]:
        self._validate_query(query)
        items = self._load_items(query)
        grouped: dict[str, list[ROIItem]] = {}
        for item in items:
            grouped.setdefault(item.match.competition, []).append(item)
        return [
            ROIGroupResult(key=league, metrics=self._summarize(grouped_items))
            for league, grouped_items in sorted(grouped.items(), key=lambda pair: pair[0].lower())
        ]

    def group_by_market(self, query: ROIQuery) -> list[ROIGroupResult]:
        self._validate_query(query)
        items = self._load_items(query)
        grouped: dict[str, list[ROIItem]] = {}
        for item in items:
            grouped.setdefault(item.pick.market, []).append(item)
        return [
            ROIGroupResult(key=market, metrics=self._summarize(grouped_items))
            for market, grouped_items in sorted(grouped.items(), key=lambda pair: pair[0].lower())
        ]

    def _load_items(self, query: ROIQuery) -> list[ROIItem]:
        items: list[ROIItem] = []
        for day in self._date_range(query.start_date, query.end_date):
            for result in self._results.list_results_for_day(day):
                pick = self._picks.get_pick(result.pick_id)
                if pick is None:
                    continue
                if query.market is not None and pick.market != query.market:
                    continue

                match = self._matches.get_match(pick.match_id)
                if match is None:
                    continue
                if query.league is not None and match.competition != query.league:
                    continue

                items.append(ROIItem(match=match, pick=pick, result=result))
        return items

    @staticmethod
    def _validate_query(query: ROIQuery) -> None:
        if query.end_date < query.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")

    @staticmethod
    def _summarize(items: list[ROIItem]) -> ROIResult:
        total_stake = sum(Decimal(str(item.result.stake_units)) for item in items)
        total_profit = sum(Decimal(str(item.result.profit_units)) for item in items)
        wins = sum(1 for item in items if item.result.status == "won")
        losses = sum(1 for item in items if item.result.status == "lost")
        pushes = sum(1 for item in items if item.result.status == "push")

        roi = None
        if total_stake != Decimal("0"):
            roi = float((total_profit / total_stake).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP))

        return ROIResult(
            total_bets=len(items),
            total_stake=float(total_stake.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)),
            total_profit=float(total_profit.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)),
            roi=roi,
            wins=wins,
            losses=losses,
            pushes=pushes,
        )

    @staticmethod
    def _date_range(start_date: date, end_date: date):
        cursor = start_date
        while cursor <= end_date:
            yield cursor
            cursor += timedelta(days=1)

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
