from __future__ import annotations

from backend.app.repositories.providers.espn import extract_supported_odds


def test_extract_supported_odds_includes_1x2_btts_and_total_goals() -> None:
    summary = {
        "header": {
            "competitions": [
                {
                    "odds": [
                        {
                            "provider": {"name": "ESPN"},
                            "timestamp": "2026-04-20T18:30:00Z",
                            "homeTeamOdds": {"moneyLine": +120},
                            "drawOdds": {"moneyLine": +210},
                            "awayTeamOdds": {"moneyLine": +240},
                        }
                    ]
                }
            ]
        },
        "pickcenter": [
            {
                "name": "Both Teams To Score",
                "provider": {"name": "ESPN"},
                "timestamp": "2026-04-20T18:31:00Z",
                "outcomes": [
                    {"name": "Yes", "price": -110},
                    {"name": "No", "price": -105},
                ],
            },
            {
                "name": "Over/Under 2.5 Goals",
                "provider": {"name": "ESPN"},
                "timestamp": "2026-04-20T18:32:00Z",
                "outcomes": [
                    {"name": "Over 2.5", "price": -115},
                    {"name": "Under 2.5", "price": -102},
                ],
            },
        ],
    }

    snapshots = extract_supported_odds(summary)
    keys = {(item["market"], item["selection"]) for item in snapshots}

    assert ("1X2", "HOME") in keys
    assert ("1X2", "DRAW") in keys
    assert ("1X2", "AWAY") in keys
    assert ("BTTS", "YES") in keys
    assert ("BTTS", "NO") in keys
    assert ("TOTAL_GOALS", "OVER_2_5") in keys
    assert ("TOTAL_GOALS", "UNDER_2_5") in keys


def test_extract_supported_odds_deduplicates_market_selection_pairs() -> None:
    summary = {
        "header": {
            "competitions": [
                {
                    "odds": [
                        {
                            "provider": {"name": "ESPN"},
                            "timestamp": "2026-04-20T18:30:00Z",
                            "homeTeamOdds": {"moneyLine": +120},
                            "drawOdds": {"moneyLine": +210},
                            "awayTeamOdds": {"moneyLine": +240},
                        }
                    ]
                }
            ]
        },
        "pickcenter": [
            {
                "name": "Both Teams To Score",
                "provider": {"name": "ESPN"},
                "timestamp": "2026-04-20T18:31:00Z",
                "outcomes": [
                    {"name": "Yes", "price": 1.91},
                    {"name": "Yes", "price": 1.95},
                ],
            }
        ],
    }

    snapshots = extract_supported_odds(summary)
    btts_yes = [item for item in snapshots if item["market"] == "BTTS" and item["selection"] == "YES"]

    assert len(btts_yes) == 1
