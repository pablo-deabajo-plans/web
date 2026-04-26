from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.app.repositories.in_memory import InMemoryMatchRepository
from backend.app.repositories.providers.espn import season_date_range
from backend.app.services.match_ingestion import MatchIngestionService


LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")


def _history_row(
    event_id: str,
    match_date: date,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
) -> dict:
    return {
        "EventId": event_id,
        "ExternalId": event_id,
        "Date": match_date.strftime("%d/%m/%Y"),
        "MatchDate": match_date,
        "Time": "20:00",
        "HomeTeam": home_team,
        "AwayTeam": away_team,
        "HomeTeamRaw": home_team,
        "AwayTeamRaw": away_team,
        "Status": "finished",
        "FTHG": home_score,
        "FTAG": away_score,
        "FixtureLabel": f"{match_date.isoformat()} | {home_team} vs {away_team}",
        "Source": "HISTORY",
    }


def test_backfill_historical_matches_seeds_empty_repository() -> None:
    repository = InMemoryMatchRepository(matches=[])
    target_date = date(2026, 4, 20)
    season_rows = [
        _history_row("h-1", date(2026, 4, 18), "Team A", "Team C", 2, 0),
        _history_row("h-2", date(2026, 4, 17), "Team D", "Team B", 1, 1),
        _history_row("h-3", date(2026, 4, 14), "Team A", "Team E", 3, 1),
        _history_row("h-4", date(2026, 4, 12), "Team F", "Team B", 0, 2),
    ]

    service = MatchIngestionService(
        repository=repository,
        timezone=LOCAL_TIMEZONE,
        fetch_for_season=lambda *_args, **_kwargs: season_rows,
    )

    result = service.backfill_historical_matches(
        "esp.1",
        "LaLiga",
        "calendar",
        target_date,
        team_names=["Team A", "Team B"],
        matches_per_team=2,
    )

    assert len(result.stored_matches) == 4
    finished_matches = repository.list_finished_matches("LaLiga", target_date, teams=["Team A", "Team B"])
    team_a_count = sum(1 for match in finished_matches if "Team A" in {match.home_team, match.away_team})
    team_b_count = sum(1 for match in finished_matches if "Team B" in {match.home_team, match.away_team})

    assert team_a_count >= 2
    assert team_b_count >= 2
    assert all(match.status == "finished" for match in result.stored_matches)
    assert all(match.home_score is not None and match.away_score is not None for match in result.stored_matches)


def test_backfill_historical_matches_skips_fetch_when_history_already_exists() -> None:
    target_date = date(2026, 4, 20)
    repository = InMemoryMatchRepository(
        matches=[
            service_match("existing-1", datetime(2026, 4, 18, 20, 0, tzinfo=LOCAL_TIMEZONE), "Team A", "Team C"),
            service_match("existing-2", datetime(2026, 4, 16, 20, 0, tzinfo=LOCAL_TIMEZONE), "Team A", "Team D"),
        ]
    )

    fetch_called = False

    def _fetch_for_season(*_args, **_kwargs):
        nonlocal fetch_called
        fetch_called = True
        return []

    service = MatchIngestionService(
        repository=repository,
        timezone=LOCAL_TIMEZONE,
        fetch_for_season=_fetch_for_season,
    )

    result = service.backfill_historical_matches(
        "esp.1",
        "LaLiga",
        "calendar",
        target_date,
        team_names=["Team A"],
        matches_per_team=2,
    )

    assert result.stored_matches == ()
    assert fetch_called is False


def test_european_season_date_range_crosses_year_boundary() -> None:
    start_date, end_date = season_date_range("european", today=date(2026, 1, 15))

    assert start_date == "20250701"
    assert end_date == "20260630"


def service_match(match_id: str, kickoff_at: datetime, home_team: str, away_team: str):
    from backend.app.domain.models import Match

    return Match(
        id=match_id,
        external_id=match_id,
        competition="LaLiga",
        kickoff_at=kickoff_at,
        home_team=home_team,
        away_team=away_team,
        status="finished",
        source="seed",
        home_score=1,
        away_score=0,
    )
