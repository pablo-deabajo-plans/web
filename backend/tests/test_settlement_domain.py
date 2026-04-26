from __future__ import annotations

from decimal import Decimal

from backend.app.domain.settlement import settle_market_pick


def test_settle_market_pick_supports_1x2() -> None:
    decision = settle_market_pick(
        match_status="finished",
        home_team="Alpha",
        away_team="Beta",
        home_score=2,
        away_score=1,
        market="1X2",
        selection="HOME",
        stake_units=Decimal("1.0000"),
        offered_odds=Decimal("2.1000"),
    )

    assert decision is not None
    assert decision.status == "won"
    assert decision.settled_selection == "HOME"
    assert decision.profit_units == Decimal("1.1000")


def test_settle_market_pick_supports_btts() -> None:
    decision = settle_market_pick(
        match_status="finished",
        home_team="Alpha",
        away_team="Beta",
        home_score=1,
        away_score=1,
        market="BTTS",
        selection="YES",
        stake_units=Decimal("1.0000"),
        offered_odds=Decimal("1.9000"),
    )

    assert decision is not None
    assert decision.status == "won"
    assert decision.settled_selection == "YES"


def test_settle_market_pick_supports_total_goals() -> None:
    decision = settle_market_pick(
        match_status="finished",
        home_team="Alpha",
        away_team="Beta",
        home_score=2,
        away_score=0,
        market="TOTAL_GOALS",
        selection="UNDER_2_5",
        stake_units=Decimal("1.0000"),
        offered_odds=Decimal("1.9500"),
    )

    assert decision is not None
    assert decision.status == "won"
    assert decision.settled_selection == "UNDER_2_5"

