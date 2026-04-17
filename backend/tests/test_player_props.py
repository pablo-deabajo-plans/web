from backend.app.domain.player_props import (
    build_player_probabilities,
    classify_player_confidence,
    poisson_probability_over,
    weighted_mean,
)


def test_weighted_mean_returns_zero_for_empty_inputs() -> None:
    assert weighted_mean([], []) == 0.0


def test_poisson_probability_over_is_bounded() -> None:
    probability = poisson_probability_over(1.4, 0.5)
    assert 0.0 <= probability <= 1.0


def test_classify_player_confidence_thresholds() -> None:
    assert classify_player_confidence(0.80) == "Alta"
    assert classify_player_confidence(0.60) == "Media"
    assert classify_player_confidence(0.30) == "Baja"


def test_build_player_probabilities_groups_by_metric_and_team() -> None:
    payload = {
        "available": True,
        "provider": "Sportmonks",
        "fixture": {"id": 1},
        "teams": [
            {"team_id": "10", "team_name": "Home FC", "fixtures_sampled": 4},
            {"team_id": "20", "team_name": "Away FC", "fixtures_sampled": 4},
        ],
        "player_logs": [
            {"player_id": 7, "player_name": "Striker A", "team_id": 10, "team_name": "Home FC", "position": "FW", "minutes": 90, "is_starter": True, "starting_at": "2026-04-10", "stats": {"shots_on_target": 2, "shots_total": 4, "fouls_committed": 1, "fouls_drawn": 2}},
            {"player_id": 7, "player_name": "Striker A", "team_id": 10, "team_name": "Home FC", "position": "FW", "minutes": 82, "is_starter": True, "starting_at": "2026-04-01", "stats": {"shots_on_target": 1, "shots_total": 3, "fouls_committed": 0, "fouls_drawn": 1}},
            {"player_id": 9, "player_name": "Forward B", "team_id": 20, "team_name": "Away FC", "position": "FW", "minutes": 88, "is_starter": True, "starting_at": "2026-04-09", "stats": {"shots_on_target": 1, "shots_total": 2, "fouls_committed": 2, "fouls_drawn": 1}},
            {"player_id": 9, "player_name": "Forward B", "team_id": 20, "team_name": "Away FC", "position": "FW", "minutes": 76, "is_starter": True, "starting_at": "2026-04-02", "stats": {"shots_on_target": 1, "shots_total": 2, "fouls_committed": 1, "fouls_drawn": 0}},
        ],
    }

    result = build_player_probabilities(payload)

    assert result["available"] is True
    assert len(result["metrics"]) == 4
    shots_metric = next(metric for metric in result["metrics"] if metric["key"] == "shots_on_target")
    assert shots_metric["teams"][0]["players"]
