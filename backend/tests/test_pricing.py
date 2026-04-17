from backend.app.domain.pricing import build_pick, expected_edge, fair_odds, kelly_fraction


def test_fair_odds_returns_inverse_probability() -> None:
    assert fair_odds(0.5) == 2.0


def test_expected_edge_matches_existing_formula() -> None:
    assert round(expected_edge(0.55, 2.10), 4) == 0.155


def test_kelly_fraction_returns_zero_for_negative_ev() -> None:
    assert kelly_fraction(0.40, 1.80) == 0.0


def test_build_pick_computes_fair_odds_edge_and_half_kelly() -> None:
    pick = build_pick(
        match_id="match-001",
        market="1X2",
        selection="Home",
        probability=0.56,
        offered_odds=2.10,
        provider="test-book",
    )
    assert round(pick.fair_odds, 4) == 1.7857
    assert round(pick.edge, 4) == 0.176
    assert pick.stake_fraction > 0
