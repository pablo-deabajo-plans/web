from backend.app.services.value_pick_ranking import build_value_pick_ranking


def test_build_value_pick_ranking_filters_missing_markets_and_sorts_by_edge() -> None:
    items = [
        {
            "analysis": {
                "local": "Team A",
                "visitante": "Team B",
                "mercados": [
                    {"nombre": "Victoria Team A", "prob": 0.55},
                    {"nombre": "Empate", "prob": 0.25},
                ],
            },
            "auto_odds": {
                "Victoria Team A": {"odds": 2.20, "provider": "Book A"},
                "Empate": {"odds": 3.10, "provider": "Book A"},
            },
        },
        {
            "analysis": {
                "local": "Team C",
                "visitante": "Team D",
                "mercados": [
                    {"nombre": "Victoria Team C", "prob": 0.48},
                    {"nombre": "BTTS", "prob": 0.61},
                ],
            },
            "auto_odds": {
                "BTTS": {"odds": 1.95, "provider": "Book B"},
            },
        },
    ]

    ranking = build_value_pick_ranking(items, limit=10)

    assert len(ranking) == 3
    assert ranking[0]["edge"] >= ranking[1]["edge"] >= ranking[2]["edge"]
    assert ranking[0]["market"] == "Victoria Team A"
    assert all("provider" in item for item in ranking)
