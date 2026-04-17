from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

import pandas as pd

from backend.app.domain.analysis import build_insights, build_match_analysis
from backend.app.domain.models import Match
from backend.app.repositories.contracts import MatchRepository
from backend.app.repositories.providers.espn import (
    DEFAULT_TIMEZONE,
    fetch_espn_matches_for_date,
    fetch_espn_matches_for_season,
)


@dataclass(frozen=True)
class IngestedMatch:
    id: str
    competition: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    status: str
    source: str
    raw_home_team: str
    raw_away_team: str
    fixture_label: str
    home_score: int | None = None
    away_score: int | None = None
    home_corners: float | None = None
    away_corners: float | None = None
    home_shots: float | None = None
    away_shots: float | None = None
    home_shots_on_target: float | None = None
    away_shots_on_target: float | None = None

    def to_match(self) -> Match:
        return Match(
            id=self.id,
            competition=self.competition,
            kickoff_at=self.kickoff_at,
            home_team=self.home_team,
            away_team=self.away_team,
            status=self.status,
            source=self.source,
        )


@dataclass(frozen=True)
class AnalyzedMatch:
    match: IngestedMatch
    analysis: dict | None
    insights: tuple[str, ...]


class MatchIngestionServiceError(RuntimeError):
    """Raised when match ingestion cannot complete successfully."""


class MatchIngestionService:
    def __init__(
        self,
        *,
        repository: MatchRepository | None = None,
        timezone: ZoneInfo = DEFAULT_TIMEZONE,
        fetch_for_date: Callable[..., list[dict]] = fetch_espn_matches_for_date,
        fetch_for_season: Callable[..., list[dict]] = fetch_espn_matches_for_season,
    ) -> None:
        self._repository = repository
        self._timezone = timezone
        self._fetch_for_date = fetch_for_date
        self._fetch_for_season = fetch_for_season

    def ingest_espn_matches_for_date(self, league_id: str, competition: str, target_date: date) -> list[IngestedMatch]:
        rows = self._fetch_for_date(league_id, target_date, source="ESPN")
        ingested_matches = [self._normalize_match_row(row, competition=competition) for row in rows]
        return self._persist_and_reload_ingested_matches(ingested_matches, target_date)

    def ingest_espn_matches_for_season(
        self,
        league_id: str,
        competition: str,
        season_type: str,
    ) -> list[IngestedMatch]:
        rows = self._fetch_for_season(league_id, season_type, source="HISTORY")
        return [self._normalize_match_row(row, competition=competition) for row in rows]

    def ingest_domain_matches_for_date(self, league_id: str, competition: str, target_date: date) -> list[Match]:
        return [item.to_match() for item in self.ingest_espn_matches_for_date(league_id, competition, target_date)]

    def get_analyzed_matches(
        self,
        league_id: str,
        competition: str,
        target_date: date,
        *,
        season_type: str = "calendar",
    ) -> list[AnalyzedMatch]:
        matches = self.ingest_espn_matches_for_date(league_id, competition, target_date)
        historical_rows = self._fetch_for_season(league_id, season_type, source="HISTORY")
        historical_frame = self._build_historical_frame(historical_rows)

        analyzed_matches: list[AnalyzedMatch] = []
        for match in matches:
            analysis = build_match_analysis(
                historical_frame,
                competition,
                match.home_team,
                match.away_team,
                match_date=match.kickoff_at.date(),
                match_label=match.fixture_label,
            )
            insights = tuple(build_insights(analysis)) if analysis else ()
            analyzed_matches.append(
                AnalyzedMatch(
                    match=match,
                    analysis=analysis,
                    insights=insights,
                )
            )
        return analyzed_matches

    def _persist_and_reload_ingested_matches(
        self,
        matches: list[IngestedMatch],
        target_date: date,
    ) -> list[IngestedMatch]:
        if self._repository is None or not matches:
            return matches

        try:
            self._repository.upsert_matches([item.to_match() for item in matches])
            stored_matches = list(self._repository.list_matches_for_day(target_date))
        except Exception as exc:
            raise MatchIngestionServiceError("Could not persist or reload ingested matches") from exc

        ingested_by_id = {item.id: item for item in matches}
        reloaded_matches: list[IngestedMatch] = []
        for stored_match in stored_matches:
            original = ingested_by_id.get(stored_match.id)
            if original is None:
                continue
            reloaded_matches.append(
                IngestedMatch(
                    id=stored_match.id,
                    competition=stored_match.competition,
                    kickoff_at=stored_match.kickoff_at,
                    home_team=stored_match.home_team,
                    away_team=stored_match.away_team,
                    status=stored_match.status,
                    source=stored_match.source or original.source,
                    raw_home_team=original.raw_home_team,
                    raw_away_team=original.raw_away_team,
                    fixture_label=original.fixture_label,
                    home_score=original.home_score,
                    away_score=original.away_score,
                    home_corners=original.home_corners,
                    away_corners=original.away_corners,
                    home_shots=original.home_shots,
                    away_shots=original.away_shots,
                    home_shots_on_target=original.home_shots_on_target,
                    away_shots_on_target=original.away_shots_on_target,
                )
            )
        return reloaded_matches

    def _normalize_match_row(self, row: dict, *, competition: str) -> IngestedMatch:
        match_date = row.get("MatchDate")
        if not isinstance(match_date, date):
            raise ValueError(f"Expected MatchDate to be a date, got {match_date!r}")

        kickoff_at = self._build_kickoff(match_date, row.get("Time"))
        home_score = self._as_int_or_none(row.get("FTHG"))
        away_score = self._as_int_or_none(row.get("FTAG"))

        return IngestedMatch(
            id=str(row.get("EventId", "")),
            competition=competition,
            kickoff_at=kickoff_at,
            home_team=str(row.get("HomeTeam", "")),
            away_team=str(row.get("AwayTeam", "")),
            status=self._derive_status(home_score, away_score),
            source=str(row.get("Source", "ESPN")),
            raw_home_team=str(row.get("HomeTeamRaw", row.get("HomeTeam", ""))),
            raw_away_team=str(row.get("AwayTeamRaw", row.get("AwayTeam", ""))),
            fixture_label=str(row.get("FixtureLabel", "")),
            home_score=home_score,
            away_score=away_score,
            home_corners=self._as_float_or_none(row.get("HC")),
            away_corners=self._as_float_or_none(row.get("AC")),
            home_shots=self._as_float_or_none(row.get("HS")),
            away_shots=self._as_float_or_none(row.get("AS")),
            home_shots_on_target=self._as_float_or_none(row.get("HST")),
            away_shots_on_target=self._as_float_or_none(row.get("AST")),
        )

    def _build_kickoff(self, match_date: date, raw_time: object) -> datetime:
        time_text = str(raw_time or "").strip()
        try:
            kickoff_time = datetime.strptime(time_text or "00:00", "%H:%M").time()
        except ValueError as exc:
            raise ValueError(f"Invalid ESPN kickoff time: {raw_time!r}") from exc
        return datetime.combine(match_date, kickoff_time, tzinfo=self._timezone)

    @staticmethod
    def _derive_status(home_score: int | None, away_score: int | None) -> str:
        if home_score is not None and away_score is not None:
            return "completed"
        return "scheduled"

    @staticmethod
    def _build_historical_frame(rows: list[dict]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows)
        expected_columns = [
            "MatchDate",
            "Date",
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
            "Source",
            "FixtureLabel",
        ]
        for column in expected_columns:
            if column not in frame.columns:
                frame[column] = None
        return frame

    @staticmethod
    def _as_int_or_none(value: object) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Expected integer-compatible value, got {value!r}") from exc

    @staticmethod
    def _as_float_or_none(value: object) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Expected float-compatible value, got {value!r}") from exc
