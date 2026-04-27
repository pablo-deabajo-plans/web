from datetime import datetime, timezone

from backend.app.domain.models import OddsQuote
from backend.app.services.value_pick_ranking import build_value_pick_ranking


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

    assert len(ranking) == 3
    assert ranking[0]["edge"] >= ranking[1]["edge"] >= ranking[2]["edge"]
    assert ranking[0]["market"] == "Victoria Team A"
    assert all("provider" in item for item in ranking)
