from datetime import datetime

import pandas as pd

from backend.app.domain.analysis import (
    build_fallback_h2h,
    build_match_analysis,
    calculate_contextual_h2h_adjustment,
    simulate_match,
)


def _sample_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Date": "2026-01-10", "HomeTeam": "Alpha FC", "AwayTeam": "Beta FC", "FTHG": 2, "FTAG": 1, "HC": 6, "AC": 3, "HS": 14, "AS": 8, "HST": 6, "AST": 3, "HY": 2, "AY": 3},
            {"Date": "2026-01-17", "HomeTeam": "Gamma FC", "AwayTeam": "Alpha FC", "FTHG": 0, "FTAG": 1, "HC": 4, "AC": 5, "HS": 9, "AS": 12, "HST": 2, "AST": 5, "HY": 1, "AY": 2},
            {"Date": "2026-01-24", "HomeTeam": "Beta FC", "AwayTeam": "Gamma FC", "FTHG": 1, "FTAG": 1, "HC": 5, "AC": 4, "HS": 11, "AS": 10, "HST": 4, "AST": 4, "HY": 2, "AY": 2},
            {"Date": "2026-02-01", "HomeTeam": "Alpha FC", "AwayTeam": "Gamma FC", "FTHG": 3, "FTAG": 1, "HC": 7, "AC": 2, "HS": 15, "AS": 7, "HST": 7, "AST": 2, "HY": 1, "AY": 4},
            {"Date": "2026-02-08", "HomeTeam": "Beta FC", "AwayTeam": "Alpha FC", "FTHG": 0, "FTAG": 2, "HC": 3, "AC": 6, "HS": 7, "AS": 13, "HST": 2, "AST": 6, "HY": 3, "AY": 2},
            {"Date": "2026-02-15", "HomeTeam": "Gamma FC", "AwayTeam": "Beta FC", "FTHG": 2, "FTAG": 0, "HC": 6, "AC": 4, "HS": 12, "AS": 8, "HST": 5, "AST": 3, "HY": 2, "AY": 1},
        ]
    )


def test_build_match_analysis_returns_expected_shape() -> None:
    analysis = build_match_analysis(
        _sample_history(),
        liga="LaLiga",
        local="Alpha FC",
        visitante="Beta FC",
        match_date=datetime(2026, 3, 1),
        match_label="Alpha FC vs Beta FC",
    )

    assert analysis is not None
    assert analysis["liga"] == "LaLiga"
    assert analysis["local"] == "Alpha FC"
    assert analysis["visitante"] == "Beta FC"
    assert analysis["resultado"]["1"] >= 0.0
    assert analysis["resultado"]["X"] >= 0.0
    assert analysis["resultado"]["2"] >= 0.0
    assert len(analysis["mercados"]) >= 3
    assert "trace" in analysis


def test_build_fallback_h2h_uses_general_history_when_no_direct_match() -> None:
    stats_local, stats_visitante, h2h = build_fallback_h2h(_sample_history(), "Alpha FC", "Delta FC")

    assert stats_local["overall"]["pj"] > 0
    assert stats_visitante["overall"]["pj"] == 0
    assert h2h["matches"] == 0


def test_contextual_h2h_adjustment_is_bounded() -> None:
    adjustment, detail = calculate_contextual_h2h_adjustment(
        {"comparison_window": 8, "comparison_form": {"ppg": 2.2}},
        {"comparison_window": 8, "comparison_form": {"ppg": 0.8}},
        {"matches": 4, "local_win_pct": 0.75, "away_win_pct": 0.0},
    )

    assert -0.05 <= adjustment <= 0.05
    assert detail["mode"] == "h2h_plus_recent"


def test_simulate_match_is_deterministic_with_analytical_model() -> None:
    first = simulate_match(1.4, 0.9, 5.2, 4.7, 2.1, 2.3, 12.0, 10.0, 4.5, 3.8)
    second = simulate_match(1.4, 0.9, 5.2, 4.7, 2.1, 2.3, 12.0, 10.0, 4.5, 3.8)

    assert first == second
    assert first["Marcador"]
    assert len(first["TopScores"]) == 3
    assert abs((first["1"] + first["X"] + first["2"]) - 1.0) < 0.001
