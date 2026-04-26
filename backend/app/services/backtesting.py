from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import json
from uuid import uuid4

import pandas as pd

from backend.app.core.logging import get_logger
from backend.app.core.time import utc_now
from backend.app.domain.analysis import build_match_analysis
from backend.app.domain.pick_generation import MODEL_VERSION, analysis_id_for_match, build_picks_for_analysis
from backend.app.domain.settlement import SettlementDecision, settle_market_pick


LOGGER = get_logger(__name__)
MONEY_PRECISION = Decimal("0.0001")
ROI_PRECISION = Decimal("0.000001")

HISTORICAL_QUERY = """
SELECT
    competition,
    kickoff_at,
    TO_CHAR(kickoff_at AT TIME ZONE 'UTC', 'DD/MM/YYYY') AS "Date",
    (kickoff_at AT TIME ZONE 'UTC')::date AS "MatchDate",
    TO_CHAR(kickoff_at AT TIME ZONE 'UTC', 'HH24:MI') AS "Time",
    home_team AS "HomeTeam",
    away_team AS "AwayTeam",
    home_score AS "FTHG",
    away_score AS "FTAG",
    home_corners AS "HC",
    away_corners AS "AC",
    home_shots AS "HS",
    away_shots AS "AS",
    home_shots_on_target AS "HST",
    away_shots_on_target AS "AST"
FROM matches
WHERE LOWER(COALESCE(status, '')) = 'finished'
  AND home_score IS NOT NULL
  AND away_score IS NOT NULL
  AND (kickoff_at AT TIME ZONE 'UTC')::date <= %s
ORDER BY competition ASC, kickoff_at ASC
"""

FINISHED_MATCHES_QUERY = """
SELECT
    id,
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
FROM matches
WHERE LOWER(COALESCE(status, '')) = 'finished'
  AND home_score IS NOT NULL
  AND away_score IS NOT NULL
  AND (kickoff_at AT TIME ZONE 'UTC')::date >= %s
  AND (kickoff_at AT TIME ZONE 'UTC')::date <= %s
ORDER BY kickoff_at ASC
"""

ODDS_FOR_MATCH_QUERY = """
SELECT id, match_id, market, selection, decimal_odds, sportsbook, captured_at
FROM odds
WHERE match_id = %s
ORDER BY captured_at DESC
"""

INSERT_BACKTEST_RUN_QUERY = """
INSERT INTO backtest_runs (
    id,
    model_version,
    start_date,
    end_date,
    filters,
    total_matches,
    analyzed_matches,
    total_picks,
    resolved_bets,
    wins,
    losses,
    pushes,
    voids,
    hit_rate,
    total_stake,
    total_profit,
    roi,
    completed_at
)
VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_BACKTEST_GROUP_QUERY = """
INSERT INTO backtest_run_groups (
    run_id,
    group_type,
    group_key,
    league,
    market,
    total_bets,
    wins,
    losses,
    pushes,
    voids,
    hit_rate,
    total_stake,
    total_profit,
    roi
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (run_id, group_type, group_key) DO UPDATE SET
    league = EXCLUDED.league,
    market = EXCLUDED.market,
    total_bets = EXCLUDED.total_bets,
    wins = EXCLUDED.wins,
    losses = EXCLUDED.losses,
    pushes = EXCLUDED.pushes,
    voids = EXCLUDED.voids,
    hit_rate = EXCLUDED.hit_rate,
    total_stake = EXCLUDED.total_stake,
    total_profit = EXCLUDED.total_profit,
    roi = EXCLUDED.roi
"""

INSERT_BACKTEST_PICK_QUERY = """
INSERT INTO backtest_picks (
    id,
    run_id,
    match_id,
    analysis_id,
    competition,
    kickoff_at,
    market,
    selection,
    probability,
    fair_odds,
    offered_odds,
    edge,
    stake_units,
    provider,
    result_status,
    settled_selection,
    profit_units
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


@dataclass(frozen=True)
class BacktestPickResult:
    id: str
    match_id: str
    analysis_id: str
    competition: str
    kickoff_at: datetime
    market: str
    selection: str
    probability: float
    fair_odds: float
    offered_odds: float
    edge: float
    stake_units: Decimal
    provider: str | None
    result_status: str
    settled_selection: str | None
    profit_units: Decimal


@dataclass(frozen=True)
class BacktestSummary:
    total_bets: int
    resolved_bets: int
    wins: int
    losses: int
    pushes: int
    voids: int
    hit_rate: float | None
    total_stake: float
    total_profit: float
    roi: float | None


@dataclass(frozen=True)
class BacktestRunResult:
    run_id: str
    start_date: date
    end_date: date
    total_matches: int
    analyzed_matches: int
    total_picks: int
    summary: BacktestSummary
    by_league: dict[str, BacktestSummary]
    by_market: dict[str, BacktestSummary]


class BacktestingService:
    def __init__(self, connection_factory) -> None:
        self._connection_factory = connection_factory

    def run(self, *, start_date: date, end_date: date) -> BacktestRunResult:
        if end_date < start_date:
            raise ValueError("BACKTEST_END_DATE must be greater than or equal to BACKTEST_START_DATE")

        run_id = str(uuid4())
        historical_frames = self._load_historical_frames(end_date)
        matches = self._load_finished_matches(start_date, end_date)

        pick_results: list[BacktestPickResult] = []
        analyzed_matches = 0

        for match in matches:
            historical_frame = self._frame_for_match(historical_frames.get(match["competition"]), match["kickoff_at"])
            if historical_frame.empty:
                continue

            analysis = build_match_analysis(
                historical_frame,
                match["competition"],
                match["home_team"],
                match["away_team"],
                match_date=match["kickoff_at"].date(),
                match_label=f"{match['kickoff_at'].isoformat()} | {match['home_team']} vs {match['away_team']}",
            )
            if analysis is None:
                continue

            analyzed_matches += 1
            analysis_id = analysis_id_for_match(match["id"], MODEL_VERSION)
            quotes = self._load_quotes_for_match(match["id"], match["kickoff_at"])
            picks, _ = build_picks_for_analysis(_BacktestMatchView.from_row(match), analysis, analysis_id, quotes)
            for pick in picks:
                decision = settle_market_pick(
                    match_status=match["status"],
                    home_team=match["home_team"],
                    away_team=match["away_team"],
                    home_score=match["home_score"],
                    away_score=match["away_score"],
                    market=pick.market,
                    selection=pick.selection,
                    stake_units=Decimal(str(pick.stake_units or 0)),
                    offered_odds=Decimal(str(pick.offered_odds)),
                )
                if decision is None:
                    continue
                pick_results.append(self._to_pick_result(run_id, pick, match, decision))

        overall = self._summarize(pick_results)
        by_league = self._group_summaries(pick_results, key_fn=lambda item: item.competition)
        by_market = self._group_summaries(pick_results, key_fn=lambda item: item.market)

        self._store_run(
            run_id=run_id,
            start_date=start_date,
            end_date=end_date,
            total_matches=len(matches),
            analyzed_matches=analyzed_matches,
            picks=pick_results,
            overall=overall,
            by_league=by_league,
            by_market=by_market,
        )

        LOGGER.info(
            json.dumps(
                {
                    "event": "backtest_completed",
                    "run_id": run_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "total_matches": len(matches),
                    "analyzed_matches": analyzed_matches,
                    "total_picks": len(pick_results),
                    "roi": overall.roi,
                    "hit_rate": overall.hit_rate,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )

        return BacktestRunResult(
            run_id=run_id,
            start_date=start_date,
            end_date=end_date,
            total_matches=len(matches),
            analyzed_matches=analyzed_matches,
            total_picks=len(pick_results),
            summary=overall,
            by_league=by_league,
            by_market=by_market,
        )

    def _load_historical_frames(self, end_date: date) -> dict[str, pd.DataFrame]:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(HISTORICAL_QUERY, (end_date,))
                rows = cursor.fetchall()

        if not rows:
            return {}

        frame = pd.DataFrame(
            rows,
            columns=[
                "competition",
                "KickoffAt",
                "Date",
                "MatchDate",
                "Time",
                "HomeTeam",
                "AwayTeam",
                "FTHG",
                "FTAG",
                "HC",
                "AC",
                "HS",
                "AS",
                "HST",
                "AST",
            ],
        )
        frame["Source"] = "DB"
        return {
            competition: competition_frame.reset_index(drop=True)
            for competition, competition_frame in frame.groupby("competition", sort=False)
        }

    def _load_finished_matches(self, start_date: date, end_date: date) -> list[dict]:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(FINISHED_MATCHES_QUERY, (start_date, end_date))
                rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "competition": row[1],
                "kickoff_at": row[2],
                "home_team": row[3],
                "away_team": row[4],
                "status": row[5],
                "source": row[6],
                "home_score": row[7],
                "away_score": row[8],
                "home_corners": row[9],
                "away_corners": row[10],
                "home_shots": row[11],
                "away_shots": row[12],
                "home_shots_on_target": row[13],
                "away_shots_on_target": row[14],
            }
            for row in rows
        ]

    def _frame_for_match(self, competition_frame: pd.DataFrame | None, kickoff_at: datetime) -> pd.DataFrame:
        if competition_frame is None or competition_frame.empty:
            return pd.DataFrame()
        return competition_frame[competition_frame["KickoffAt"] < kickoff_at].drop(columns=["competition"], errors="ignore")

    def _load_quotes_for_match(self, match_id: str, kickoff_at: datetime) -> list[_BacktestQuoteView]:
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(ODDS_FOR_MATCH_QUERY, (match_id,))
                rows = cursor.fetchall()

        quotes = [
            _BacktestQuoteView(
                id=row[0],
                match_id=row[1],
                market=row[2],
                selection=row[3],
                decimal_odds=float(row[4]),
                sportsbook=row[5],
                captured_at=row[6],
            )
            for row in rows
        ]
        if not quotes:
            return []

        by_key: dict[tuple[str, str], _BacktestQuoteView] = {}
        for quote in quotes:
            key = (quote.market, quote.selection)
            existing = by_key.get(key)
            quote_is_pre_match = quote.captured_at <= kickoff_at
            existing_is_pre_match = existing is not None and existing.captured_at <= kickoff_at
            if existing is None:
                by_key[key] = quote
                continue
            if quote_is_pre_match and not existing_is_pre_match:
                by_key[key] = quote
                continue
            if quote_is_pre_match == existing_is_pre_match and quote.captured_at > existing.captured_at:
                by_key[key] = quote
        return list(by_key.values())

    def _to_pick_result(
        self,
        run_id: str,
        pick,
        match: dict,
        decision: SettlementDecision,
    ) -> BacktestPickResult:
        return BacktestPickResult(
            id=f"{run_id}:{pick.id}",
            match_id=pick.match_id,
            analysis_id=pick.analysis_id or analysis_id_for_match(pick.match_id, MODEL_VERSION),
            competition=match["competition"],
            kickoff_at=match["kickoff_at"],
            market=pick.market,
            selection=pick.selection,
            probability=float(pick.probability),
            fair_odds=float(pick.fair_odds),
            offered_odds=float(pick.offered_odds),
            edge=float(pick.edge),
            stake_units=Decimal(str(pick.stake_units or 0)).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP),
            provider=pick.provider,
            result_status=decision.status,
            settled_selection=decision.settled_selection,
            profit_units=decision.profit_units.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP),
        )

    def _summarize(self, picks: list[BacktestPickResult]) -> BacktestSummary:
        wins = sum(1 for item in picks if item.result_status == "won")
        losses = sum(1 for item in picks if item.result_status == "lost")
        pushes = sum(1 for item in picks if item.result_status == "push")
        voids = sum(1 for item in picks if item.result_status == "void")
        resolved_bets = wins + losses
        total_stake = sum(item.stake_units for item in picks)
        total_profit = sum(item.profit_units for item in picks)

        roi = None
        if total_stake != Decimal("0"):
            roi = float((total_profit / total_stake).quantize(ROI_PRECISION, rounding=ROUND_HALF_UP))

        hit_rate = None
        if resolved_bets > 0:
            hit_rate = float((Decimal(wins) / Decimal(resolved_bets)).quantize(ROI_PRECISION, rounding=ROUND_HALF_UP))

        return BacktestSummary(
            total_bets=len(picks),
            resolved_bets=resolved_bets,
            wins=wins,
            losses=losses,
            pushes=pushes,
            voids=voids,
            hit_rate=hit_rate,
            total_stake=float(total_stake.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)),
            total_profit=float(total_profit.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)),
            roi=roi,
        )

    def _group_summaries(self, picks: list[BacktestPickResult], *, key_fn) -> dict[str, BacktestSummary]:
        grouped: dict[str, list[BacktestPickResult]] = {}
        for item in picks:
            grouped.setdefault(str(key_fn(item)), []).append(item)
        return {key: self._summarize(items) for key, items in sorted(grouped.items(), key=lambda pair: pair[0].lower())}

    def _store_run(
        self,
        *,
        run_id: str,
        start_date: date,
        end_date: date,
        total_matches: int,
        analyzed_matches: int,
        picks: list[BacktestPickResult],
        overall: BacktestSummary,
        by_league: dict[str, BacktestSummary],
        by_market: dict[str, BacktestSummary],
    ) -> None:
        completed_at = utc_now()
        with self._connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    INSERT_BACKTEST_RUN_QUERY,
                    (
                        run_id,
                        MODEL_VERSION,
                        start_date,
                        end_date,
                        json.dumps({}, ensure_ascii=True),
                        total_matches,
                        analyzed_matches,
                        len(picks),
                        overall.resolved_bets,
                        overall.wins,
                        overall.losses,
                        overall.pushes,
                        overall.voids,
                        overall.hit_rate,
                        overall.total_stake,
                        overall.total_profit,
                        overall.roi,
                        completed_at,
                    ),
                )
                for item in picks:
                    cursor.execute(
                        INSERT_BACKTEST_PICK_QUERY,
                        (
                            item.id,
                            run_id,
                            item.match_id,
                            item.analysis_id,
                            item.competition,
                            item.kickoff_at,
                            item.market,
                            item.selection,
                            item.probability,
                            item.fair_odds,
                            item.offered_odds,
                            item.edge,
                            float(item.stake_units),
                            item.provider,
                            item.result_status,
                            item.settled_selection,
                            float(item.profit_units),
                        ),
                    )
                self._store_group(cursor, run_id, "overall", "overall", None, None, overall)
                for league, summary in by_league.items():
                    self._store_group(cursor, run_id, "league", league, league, None, summary)
                for market, summary in by_market.items():
                    self._store_group(cursor, run_id, "market", market, None, market, summary)
            conn.commit()

    @staticmethod
    def _store_group(cursor, run_id: str, group_type: str, group_key: str, league: str | None, market: str | None, summary: BacktestSummary) -> None:
        cursor.execute(
            INSERT_BACKTEST_GROUP_QUERY,
            (
                run_id,
                group_type,
                group_key,
                league,
                market,
                summary.total_bets,
                summary.wins,
                summary.losses,
                summary.pushes,
                summary.voids,
                summary.hit_rate,
                summary.total_stake,
                summary.total_profit,
                summary.roi,
            ),
        )


@dataclass(frozen=True)
class _BacktestQuoteView:
    id: str
    match_id: str
    market: str
    selection: str
    decimal_odds: float
    sportsbook: str | None
    captured_at: datetime


@dataclass(frozen=True)
class _BacktestMatchView:
    id: str
    home_team: str
    away_team: str

    @classmethod
    def from_row(cls, row: dict) -> "_BacktestMatchView":
        return cls(id=str(row["id"]), home_team=str(row["home_team"]), away_team=str(row["away_team"]))

