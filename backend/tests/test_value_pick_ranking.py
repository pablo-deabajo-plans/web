from datetime import datetime, timedelta, timezone

from backend.app.domain.analysis import build_match_analysis, poisson_probability_over
from backend.app.domain.market_odds import canonical_market_from_quote, compare_analysis_to_quotes
from backend.app.domain.models import OddsQuote
from backend.app.services.value_pick_ranking import build_value_pick_ranking
from backend.tests.test_analysis import _sample_history


def test_build_value_pick_ranking_filters_missing_markets_and_sorts_by_edge() -> None:
    now = datetime.now(timezone.utc)
    items = [
        {
            "analysis": {
                "local": "Team A",
                "visitante": "Team B",
                "mercados": [
                    {"nombre": "Victoria Team A", "prob": 0.55},
                    {"nombre": "Empate", "prob": 0.25},
                ],
                "stats_local": {"overall": {"pj": 12}},
                "stats_visitante": {"overall": {"pj": 12}},
            },
            "quotes": [
                OddsQuote(match_id="m1", market="1X2", selection="HOME", decimal_odds=2.20, sportsbook="Book A", captured_at=now, id="q1"),
                OddsQuote(match_id="m1", market="1X2", selection="DRAW", decimal_odds=3.10, sportsbook="Book A", captured_at=now, id="q2"),
            ],
        },
        {
            "analysis": {
                "local": "Team C",
                "visitante": "Team D",
                "mercados": [
                    {"nombre": "Victoria Team C", "prob": 0.48},
                    {"nombre": "Ambos marcan", "prob": 0.61},
                ],
                "stats_local": {"overall": {"pj": 8}},
                "stats_visitante": {"overall": {"pj": 10}},
            },
            "quotes": [
                OddsQuote(match_id="m2", market="BTTS", selection="YES", decimal_odds=1.95, sportsbook="Book B", captured_at=now, id="q3"),
            ],
        },
    ]

    ranking = build_value_pick_ranking(items, limit=10)

    assert len(ranking) == 2
    assert ranking[0]["edge"] >= ranking[1]["edge"]
    assert ranking[0]["market"] == "Victoria Team A"
    assert all("provider" in item for item in ranking)


def test_compare_analysis_to_quotes_uses_best_price_and_exact_line() -> None:
    now = datetime.now(timezone.utc)
    analysis = build_match_analysis(
        _sample_history(),
        liga="LaLiga",
        local="Alpha FC",
        visitante="Beta FC",
        match_date=datetime(2026, 3, 1),
        match_label="Alpha FC vs Beta FC",
    )
    assert analysis is not None
    quotes = [
        OddsQuote(match_id="m1", market="TOTAL_CORNERS", selection="OVER_8_5", decimal_odds=1.80, sportsbook="Book A", captured_at=now, id="q1"),
        OddsQuote(match_id="m1", market="TOTAL_CORNERS", selection="OVER_8_5", decimal_odds=2.10, sportsbook="Book B", captured_at=now, id="q2"),
    ]

    rows = compare_analysis_to_quotes(analysis, quotes)

    assert len(rows) == 1
    assert rows[0]["market"] == "Over 8.5 corners"
    assert rows[0]["best_odds"] == 2.10
    assert rows[0]["provider"] == "Book B"
    assert rows[0]["number_of_bookmakers"] == 2
    assert len(rows[0]["quote_audit"]) == 2
    assert rows[0]["prob"] == poisson_probability_over(analysis.resultado.total_corners, 8.5)


def test_compare_analysis_to_quotes_discards_stale_and_unmapped_quotes() -> None:
    now = datetime.now(timezone.utc)
    analysis = build_match_analysis(
        _sample_history(),
        liga="LaLiga",
        local="Alpha FC",
        visitante="Beta FC",
        match_date=datetime(2026, 3, 1),
        match_label="Alpha FC vs Beta FC",
    )
    assert analysis is not None
    quotes = [
        OddsQuote(match_id="m1", market="TOTAL_CORNERS", selection="OVER_8_5", decimal_odds=2.10, sportsbook="Book A", captured_at=now - timedelta(days=5), id="q1"),
        OddsQuote(match_id="m1", market="PLAYER_SHOTS", selection="Striker OVER_1_5", decimal_odds=2.00, sportsbook="Book A", captured_at=now, id="q2"),
    ]

    rows = compare_analysis_to_quotes(analysis, quotes)

    assert rows == []
    assert canonical_market_from_quote(quotes[1], analysis.local, analysis.visitante) is None
