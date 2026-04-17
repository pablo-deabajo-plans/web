from datetime import datetime, timezone

from backend.app.domain.models import Match, OddsQuote, PlayerProp
from backend.app.domain.pricing import build_pick
from backend.app.repositories.in_memory import (
    InMemoryMatchRepository,
    InMemoryOddsRepository,
    InMemoryPickRepository,
)
from backend.workers.ingest_matches import run_match_ingestion
from backend.workers.ingest_odds import run_odds_ingestion
from backend.workers.precompute_analyses import run_prediction_precompute


def test_match_ingestion_persists_matches() -> None:
    now = datetime.now(timezone.utc)
    repository = InMemoryMatchRepository(matches=[])
    count = run_match_ingestion(
        target_date=now.date(),
        fetch_matches=lambda _: [Match(id="m-1", competition="LaLiga", kickoff_at=now, home_team="A", away_team="B")],
        repository=repository,
    )

    assert count == 1
    assert repository.get_match("m-1") is not None


def test_odds_ingestion_persists_quotes() -> None:
    now = datetime.now(timezone.utc)
    repository = InMemoryOddsRepository(quotes=[])
    count = run_odds_ingestion(
        target_date=now.date(),
        fetch_odds=lambda _: [OddsQuote(id="o-1", match_id="m-1", market="1X2", selection="Home", decimal_odds=2.0, sportsbook="test", captured_at=now)],
        repository=repository,
    )

    assert count == 1
    assert len(repository.list_odds_for_match("m-1")) == 1


def test_precompute_predictions_saves_picks() -> None:
    now = datetime.now(timezone.utc)
    match_repository = InMemoryMatchRepository(
        matches=[Match(id="m-1", competition="LaLiga", kickoff_at=now, home_team="A", away_team="B")]
    )
    pick_repository = InMemoryPickRepository(picks=[], player_props=[])

    count = run_prediction_precompute(
        target_date=now.date(),
        match_repository=match_repository,
        pick_repository=pick_repository,
        compute_for_match=lambda _: (
            [build_pick(match_id="m-1", market="1X2", selection="Home", probability=0.55, offered_odds=2.1, pick_id="pick-1", created_at=now)],
            [PlayerProp(match_id="m-1", player_id="7", player_name="Player A", metric="shots_on_target", line=0.5, probability=0.61, expected_value=0.9, confidence_label="Media", generated_at=now)],
        ),
    )

    assert count == 1
    assert pick_repository.get_pick("pick-1") is not None
