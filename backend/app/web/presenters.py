from __future__ import annotations

from html import escape
import math

from backend.app.domain.analysis import poisson_probability_over


MATCH_TABS = (
    ("summary", "Resumen ejecutivo"),
    ("projection", "Proyección del partido"),
    ("odds", "Cuotas y valor"),
    ("season", "Estadísticas de temporada"),
    ("compare", "Comparativa & H2H"),
    ("players", "Jugadores"),
)

PROJECTION_MIN_PROBABILITIES = (0.2, 0.3, 0.4, 0.5, 0.6)
PROJECTION_NEAR_CERTAINTY = 0.985
PROJECTION_MAX_ROWS = 24

PROJECTION_STATS = (
    {"key": "corners", "label": "Corners"},
    {"key": "goals", "label": "Goles"},
    {"key": "fouls", "label": "Faltas"},
    {"key": "shots", "label": "Remates"},
    {"key": "shots_on_target", "label": "Remates a puerta"},
    {"key": "cards", "label": "Tarjetas"},
)

_PROJECTION_CONFIGS = {
    "corners": {
        "flag": "has_corners",
        "scopes": (
            {"key": "total", "label": "Total partido", "mean": "total_corners", "line_start": 0.5},
            {"key": "home", "label": "Local", "mean": "home_corners", "line_start": 0.5},
            {"key": "away", "label": "Visitante", "mean": "away_corners", "line_start": 0.5},
        ),
    },
    "goals": {
        "flag": None,
        "scopes": (
            {"key": "total", "label": "Total partido", "mean": "total_goals", "line_start": 0.5},
            {"key": "home", "label": "Local", "mean": "xg_local", "line_start": 0.5},
            {"key": "away", "label": "Visitante", "mean": "xg_visitante", "line_start": 0.5},
        ),
    },
    "fouls": {
        "flag": "has_fouls",
        "scopes": (
            {"key": "total", "label": "Total partido", "mean": "total_fouls", "line_start": 0.5},
        ),
    },
    "shots": {
        "flag": "has_shots",
        "scopes": (
            {"key": "total", "label": "Total partido", "mean": "total_shots", "line_start": 0.5},
            {"key": "home", "label": "Local", "mean": "home_shots", "line_start": 0.5},
            {"key": "away", "label": "Visitante", "mean": "away_shots", "line_start": 0.5},
        ),
    },
    "shots_on_target": {
        "flag": "has_shots_on_target",
        "scopes": (
            {"key": "total", "label": "Total partido", "mean": "total_shots_on_target", "line_start": 0.5},
            {"key": "home", "label": "Local", "mean": "home_shots_on_target", "line_start": 0.5},
            {"key": "away", "label": "Visitante", "mean": "away_shots_on_target", "line_start": 0.5},
        ),
    },
    "cards": {
        "flag": "has_cards",
        "scopes": (
            {"key": "total", "label": "Total partido", "mean": "total_cards", "line_start": 0.5},
        ),
    },
}


def fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.1f}%"


def fmt_num(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


def fmt_edge(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:+.2f}%"


def build_match_executive_summary(analysis: dict, odds_rows: list[dict]) -> str:
    result = analysis["resultado"]
    local = analysis["local"]
    away = analysis["visitante"]

    probs = {
        "1": float(result["home_win"]),
        "X": float(result["draw"]),
        "2": float(result["away_win"]),
    }
    ordered = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    lead_key, lead_prob = ordered[0]
    second_prob = ordered[1][1]
    margin = lead_prob - second_prob

    lead_label = {"1": local, "X": "empate", "2": away}[lead_key]
    if margin >= 0.12:
        conviction = "sesgo claro"
    elif margin >= 0.06:
        conviction = "sesgo moderado"
    else:
        conviction = "partido abierto"

    xg_local = float(analysis["xg_local"])
    xg_away = float(analysis["xg_visitante"])
    xg_total = xg_local + xg_away
    xg_diff = xg_local - xg_away

    if xg_diff >= 0.3:
        xg_read = f"{local} genera la ventaja principal en volumen ({xg_local:.2f} xG vs {xg_away:.2f})."
    elif xg_diff <= -0.3:
        xg_read = f"{away} genera la ventaja principal en volumen ({xg_away:.2f} xG vs {xg_local:.2f})."
    else:
        xg_read = f"El reparto de xG es corto ({xg_local:.2f} vs {xg_away:.2f}), sin superioridad ofensiva amplia."

    corners = float(result["total_corners"])
    corners_read = f"El modelo proyecta {corners:.2f} corners."
    if corners >= 10:
        corners_read += " El ritmo esperado de llegadas es suficiente para sostener un partido activo en volumen."
    elif corners <= 8:
        corners_read += " El volumen esperado es contenido y deja menos margen para mercados altos."
    else:
        corners_read += " La lectura de volumen es intermedia, sin exceso de conviccion en ese mercado."

    positive_edges = sorted((row for row in odds_rows if float(row["edge"]) > 0), key=lambda item: item["edge"], reverse=True)
    if positive_edges:
        top_edges = positive_edges[:2]
        markets = ", ".join(f"{row['market']} ({row['edge'] * 100:+.2f}%)" for row in top_edges)
        edge_read = f"Hay edge positivo en {markets}."
        if float(top_edges[0]["edge"]) < 0.03:
            edge_read += " La ventaja existe, pero es fina y sensible a cualquier ajuste de precio."
        else:
            edge_read += " El precio supera la cuota justa del modelo y da argumento de entrada."
    else:
        edge_read = "No hay edge positivo claro en las cuotas detectadas; el principal riesgo es forzar una entrada sin ventaja de precio."

    advantage = f"Ventaja: 1X2 con {conviction} hacia {lead_label} ({lead_prob * 100:.1f}%) y xG total de {xg_total:.2f}."
    risk = (
        f"Riesgo: el segundo escenario del 1X2 queda en {second_prob * 100:.1f}%"
        if margin < 0.1
        else f"Riesgo: aun con sesgo definido, el empate sigue vivo en {probs['X'] * 100:.1f}%"
    )
    risk += " y el valor final depende de que la cuota mantenga ventaja frente al precio justo."

    return " ".join(
        [
            f"Lectura base: el 1X2 apunta a {lead_label} con {lead_prob * 100:.1f}% y deja un {conviction}.",
            xg_read,
            corners_read,
            edge_read,
            advantage,
            risk,
        ]
    )


def match_signal_cards(analysis: dict) -> list[dict]:
    result = analysis["resultado"]
    return [
        {"label": f"Victoria {analysis['local']}", "value": result["home_win"]},
        {"label": "Empate", "value": result["draw"]},
        {"label": f"Victoria {analysis['visitante']}", "value": result["away_win"]},
        {"label": "Ambos marcan", "value": result["both_teams_score"]},
        {"label": "Over 2.5", "value": result["over_2_5_goals"]},
        {"label": "Over 9.5 corners", "value": result["over_9_5_corners"]},
    ]


def projection_stat_options() -> tuple[dict, ...]:
    return PROJECTION_STATS


def projection_min_probability_options() -> tuple[float, ...]:
    return PROJECTION_MIN_PROBABILITIES


def _projection_mean(analysis: dict, mean_key: str) -> float | None:
    result = analysis["resultado"]
    if mean_key == "xg_local":
        return float(analysis["xg_local"])
    if mean_key == "xg_visitante":
        return float(analysis["xg_visitante"])
    if mean_key == "total_shots":
        return float(result["home_shots"]) + float(result["away_shots"])
    if mean_key == "total_shots_on_target":
        return float(result["home_shots_on_target"]) + float(result["away_shots_on_target"])
    if mean_key == "total_fouls":
        return None
    value = result.get(mean_key)
    return float(value) if value is not None else None


def _projection_scope_available(analysis: dict, stat_key: str, scope_key: str, flag: str | None) -> bool:
    if flag is None:
        return True
    if flag == "has_fouls":
        return False

    local_home = analysis["stats_local"]["home"].get(flag, False)
    away_away = analysis["stats_visitante"]["away"].get(flag, False)
    if scope_key == "home":
        return bool(local_home)
    if scope_key == "away":
        return bool(away_away)
    if stat_key in {"corners", "shots", "shots_on_target", "cards"}:
        return bool(local_home and away_away)
    return False


def _projection_threshold_rows(mean: float, min_probability: float, line_start: float) -> list[dict]:
    if mean <= 0:
        return []

    max_line = max(line_start, math.ceil(mean + (5 * math.sqrt(mean + 1.0))) + 0.5)
    candidates = []
    line = line_start
    while line <= max_line:
        probability = poisson_probability_over(mean, line)
        candidates.append((line, probability))
        line += 1.0

    start_index = next(
        (index for index, (_, probability) in enumerate(candidates) if probability <= PROJECTION_NEAR_CERTAINTY),
        0,
    )

    rows = []
    for line, probability in candidates[start_index:]:
        if probability < min_probability:
            break
        rows.append({"threshold": f"Over {line:.1f}", "probability": probability})
        if len(rows) >= PROJECTION_MAX_ROWS:
            break
    return rows


def build_projection_distribution(analysis: dict, stat_key: str, min_probability: float) -> dict:
    config = _PROJECTION_CONFIGS.get(stat_key) or _PROJECTION_CONFIGS["corners"]
    selected_label = next((item["label"] for item in PROJECTION_STATS if item["key"] == stat_key), "Corners")
    min_probability = max(0.05, min(0.95, float(min_probability)))
    scopes = []

    for scope in config["scopes"]:
        scope_key = str(scope["key"])
        available = _projection_scope_available(analysis, stat_key, scope_key, config["flag"])
        mean = _projection_mean(analysis, str(scope["mean"])) if available else None
        rows = _projection_threshold_rows(float(mean), min_probability, float(scope["line_start"])) if mean is not None else []
        scopes.append(
            {
                "key": scope_key,
                "label": scope["label"],
                "available": bool(available and rows),
                "mean": mean,
                "rows": rows,
                "message": "" if available else "Datos insuficientes",
            }
        )

    return {
        "stat_key": stat_key,
        "stat_label": selected_label,
        "min_probability": min_probability,
        "scopes": scopes,
        "has_rows": any(scope["available"] for scope in scopes),
    }


def top_value_rows(odds_rows: list[dict], limit: int = 6) -> list[dict]:
    return sorted(odds_rows, key=lambda row: float(row["edge"]), reverse=True)[:limit]


def flatten_player_rows(player_payload: dict, limit: int = 12) -> list[dict]:
    rows: list[dict] = []
    if not player_payload.get("available"):
        return rows
    for metric in player_payload.get("metrics", []):
        for team in metric.get("teams", []):
            for player in team.get("players", []):
                rows.append(
                    {
                        "metric": metric["label"],
                        "line_label": metric["line_label"],
                        "team_name": team.get("team_name", "Equipo"),
                        "player_name": player.get("player_name", "Jugador"),
                        "probability": float(player.get("probability", 0.0)),
                        "expected": float(player.get("expected", 0.0)),
                        "sample": int(player.get("sample", 0) or 0),
                        "confidence_label": player.get("confidence_label", "Baja"),
                    }
                )
    rows.sort(key=lambda item: (item["probability"], item["expected"], item["sample"]), reverse=True)
    return rows[:limit]


def tab_label(tab_key: str) -> str:
    return dict(MATCH_TABS).get(tab_key, MATCH_TABS[0][1])


def safe_text(value: str) -> str:
    return escape(str(value))
