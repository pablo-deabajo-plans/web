from __future__ import annotations

from html import escape


MATCH_TABS = (
    ("summary", "Resumen ejecutivo"),
    ("projection", "Proyección del partido"),
    ("odds", "Cuotas y valor"),
    ("season", "Estadísticas de temporada"),
    ("compare", "Comparativa & H2H"),
    ("players", "Jugadores"),
)


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
