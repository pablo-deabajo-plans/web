from __future__ import annotations

from decimal import Decimal

from backend.app.repositories.providers.espn import parse_scoreboard_event
from backend.app.services.match_ingestion import MatchIngestionService
from backend.workers.settlement_worker import SettlemablePick, _settle_pick


def _espn_event(*, state: str, completed: bool = False, detail: str | None = None) -> dict:
    return {
        "id": "event-1",
        "date": "2026-04-20T18:00:00Z",
        "competitions": [
            {
                "status": {
                    "type": {
                        "state": state,
                        "completed": completed,
                        "detail": detail or state,
                    }
                },
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "Home FC"}, "score": "1"},
                    {"homeAway": "away", "team": {"displayName": "Away FC"}, "score": "0"},
                ],
            }
        ],
    }


def test_provider_normalizes_real_match_states() -> None:
    cases = [
        ("pre", False, None, "scheduled"),
        ("in", False, None, "live"),
        ("post", True, None, "finished"),
        ("pre", False, "STATUS_POSTPONED", "postponed"),
        ("pre", False, "STATUS_CANCELED", "cancelled"),
        ("pre", False, "STATUS_SUSPENDED", "abandoned"),
    ]

    for state, completed, detail, expected_status in cases:
        row = parse_scoreboard_event(_espn_event(state=state, completed=completed, detail=detail), source="ESPN")
        assert row is not None
        assert row["Status"] == expected_status


def test_ingestion_service_preserves_canonical_void_states() -> None:
    service = MatchIngestionService()

    assert service._derive_status("cancelled", None, None) == "cancelled"
    assert service._derive_status("canceled", None, None) == "cancelled"
    assert service._derive_status("postponed", None, None) == "postponed"
    assert service._derive_status("abandoned", None, None) == "abandoned"
    assert service._derive_status("suspended", None, None) == "abandoned"
    assert service._derive_status("finished", 2, 1) == "finished"


def test_settlement_voids_cancelled_postponed_and_abandoned_matches() -> None:
    for match_status in ("cancelled", "postponed", "abandoned"):
        decision = _settle_pick(
            SettlemablePick(
                pick_id=f"pick-{match_status}",
                match_id="match-1",
                match_status=match_status,
                home_team="Home FC",
                away_team="Away FC",
                home_score=None,
                away_score=None,
                market="1X2",
                selection="HOME",
                offered_odds=Decimal("2.1000"),
                stake_units=Decimal("1.0000"),
            )
        )
        assert decision is not None
        assert decision.status == "void"
        assert decision.settled_selection == "match_void"


def test_settlement_skips_scheduled_and_live_matches() -> None:
    for match_status in ("scheduled", "live"):
        decision = _settle_pick(
            SettlemablePick(
                pick_id=f"pick-{match_status}",
                match_id="match-1",
                match_status=match_status,
                home_team="Home FC",
                away_team="Away FC",
                home_score=1,
                away_score=0,
                market="1X2",
                selection="HOME",
                offered_odds=Decimal("2.1000"),
                stake_units=Decimal("1.0000"),
            )
        )
        assert decision is None
