from __future__ import annotations

import math


PLAYER_PROP_CONFIG = {
    "shots_on_target": {"label": "Remates a puerta", "threshold": 0.5, "line_label": "1+"},
    "shots_total": {"label": "Remates", "threshold": 1.5, "line_label": "2+"},
    "fouls_committed": {"label": "Faltas cometidas", "threshold": 0.5, "line_label": "1+"},
    "fouls_drawn": {"label": "Faltas recibidas", "threshold": 0.5, "line_label": "1+"},
}


def poisson_probability_over(mean: float, threshold: float) -> float:
    if mean <= 0:
        return 0.0
    minimum = int(math.floor(threshold)) + 1
    cumulative = 0.0
    for k in range(minimum):
        cumulative += math.exp(-mean) * (mean**k) / math.factorial(k)
    return max(0.0, min(1.0, 1 - cumulative))


def weighted_mean(values: list[float], weights: list[float]) -> float:
    if not values or not weights:
        return 0.0
    total_weights = sum(weights)
    if total_weights <= 0:
        return 0.0
    return float(sum(value * weight for value, weight in zip(values, weights)) / total_weights)


def classify_player_confidence(score: float) -> str:
    if score >= 0.74:
        return "Alta"
    if score >= 0.56:
        return "Media"
    return "Baja"


def build_player_probabilities(player_payload: dict) -> dict:
    if not player_payload.get("available"):
        return {
            "available": False,
            "status": player_payload.get("status", "unavailable"),
            "message": player_payload.get("message", "La integracion de jugadores no esta disponible."),
            "fixture": player_payload.get("fixture", {}),
            "teams": player_payload.get("teams", []),
            "metrics": [],
        }

    logs = player_payload.get("player_logs", [])
    teams = player_payload.get("teams", [])
    if not logs or not teams:
        return {
            "available": False,
            "status": "no_logs",
            "message": "No hay logs de jugadores suficientes para construir probabilidades.",
            "fixture": player_payload.get("fixture", {}),
            "teams": teams,
            "metrics": [],
        }

    players: dict[tuple[str, str], dict] = {}
    ordered_logs = sorted(logs, key=lambda item: item.get("starting_at", ""), reverse=True)
    for log in ordered_logs:
        player_id = str(log.get("player_id") or log.get("player_name"))
        team_id = str(log.get("team_id"))
        key = (team_id, player_id)
        player = players.setdefault(
            key,
            {
                "team_id": team_id,
                "team_name": log.get("team_name", "Equipo"),
                "player_id": player_id,
                "player_name": log.get("player_name", "Jugador"),
                "position": log.get("position", ""),
                "entries": [],
            },
        )
        player["entries"].append(log)

    metrics = []
    for metric_key, config in PLAYER_PROP_CONFIG.items():
        team_metrics = []
        for team in teams:
            team_id = str(team.get("team_id"))
            team_name = team.get("team_name", "Equipo")
            fixtures_sampled = max(1, int(team.get("fixtures_sampled", 0) or 0))
            team_players = []
            for key, player in players.items():
                if key[0] != team_id:
                    continue
                entries = player["entries"][:6]
                appearances = [entry for entry in entries if (entry.get("minutes", 0) or 0) > 0 or (entry.get("stats", {}).get(metric_key, 0) or 0) > 0]
                if len(appearances) < 2:
                    continue

                weights = [0.88**index for index in range(len(appearances))]
                values = [float(entry.get("stats", {}).get(metric_key, 0.0) or 0.0) for entry in appearances]
                minutes = [float(entry.get("minutes", 0.0) or 0.0) for entry in appearances]
                starters = [1.0 if entry.get("is_starter") else 0.0 for entry in appearances]
                threshold = config["threshold"]

                base_mean = weighted_mean(values, weights)
                mean_minutes = weighted_mean(minutes, weights)
                starter_rate = weighted_mean(starters, weights)
                hit_rate = weighted_mean([1.0 if value > threshold else 0.0 for value in values], weights)
                appearance_rate = min(1.0, len(appearances) / max(fixtures_sampled, len(appearances)))
                sample_depth = min(1.0, len(appearances) / 5.0)
                minute_share = min(1.0, mean_minutes / 75.0)

                availability_factor = 0.35 + (0.65 * appearance_rate)
                role_factor = 0.55 + (0.45 * starter_rate)
                minute_factor = 0.55 + (0.45 * minute_share)
                adjusted_mean = base_mean * availability_factor * role_factor * minute_factor
                poisson_prob = poisson_probability_over(adjusted_mean, threshold)
                probability = max(0.01, min(0.97, (poisson_prob * 0.68) + (hit_rate * appearance_rate * 0.32)))
                confidence_score = (sample_depth * 0.34) + (appearance_rate * 0.26) + (starter_rate * 0.2) + (minute_share * 0.2)

                team_players.append(
                    {
                        "player_name": player["player_name"],
                        "position": player["position"] or "Sin rol",
                        "probability": probability,
                        "expected": adjusted_mean,
                        "hit_rate": hit_rate,
                        "sample": len(appearances),
                        "fixtures_sampled": fixtures_sampled,
                        "starter_rate": starter_rate,
                        "appearance_rate": appearance_rate,
                        "minutes": mean_minutes,
                        "confidence_score": confidence_score,
                        "confidence_label": classify_player_confidence(confidence_score),
                    }
                )

            team_players.sort(key=lambda item: (item["probability"], item["confidence_score"], item["expected"]), reverse=True)
            team_metrics.append({"team_id": team_id, "team_name": team_name, "fixtures_sampled": fixtures_sampled, "players": team_players[:6]})

        metrics.append({"key": metric_key, "label": config["label"], "threshold": config["threshold"], "line_label": config["line_label"], "teams": team_metrics})

    return {
        "available": True,
        "status": "ok",
        "provider": player_payload.get("provider", "Sportmonks"),
        "fixture": player_payload.get("fixture", {}),
        "teams": teams,
        "metrics": metrics,
    }
