from __future__ import annotations

from datetime import datetime, timezone
import math

import pandas as pd

from data.teams import clave_equipo, nombre_visual_equipo
from backend.app.domain.stats import calcular_h2h, calcular_stats, extraer_historico


VALUE_BET_THRESHOLD = 0.65
SIMULACIONES = 50000
LIGAS_FASE_ELIMINATORIA = {"Champions League", "Europa League", "Conference League", "Copa del Rey"}
DEFAULT_CORNERS_FOR = 4.5
DEFAULT_CORNERS_AGAINST = 4.5
DEFAULT_CARDS_FOR = 2.1
DEFAULT_CARDS_AGAINST = 2.1
DEFAULT_SHOTS_FOR = 11.0
DEFAULT_SHOTS_AGAINST = 11.0
DEFAULT_SHOTS_ON_TARGET_FOR = 4.0
DEFAULT_SHOTS_ON_TARGET_AGAINST = 4.0
POISSON_SCORE_MAX = 12


def model_value(stats: dict, key: str, flag: str, default: float) -> float:
    if stats.get(flag):
        return float(stats.get(key, 0.0))
    return default


def offensive_model_value(stats_focus: dict, stats_opponent: dict, key_for: str, key_against: str, flag: str, default: float) -> float:
    values = []
    if stats_focus.get(flag):
        values.append(float(stats_focus.get(key_for, 0.0)))
    if stats_opponent.get(flag):
        values.append(float(stats_opponent.get(key_against, 0.0)))
    if values:
        return float(sum(values) / len(values))
    return default


def poisson_probability_series(mean: float, max_events: int = POISSON_SCORE_MAX) -> list[float]:
    if mean <= 0:
        return [1.0] + [0.0] * max_events
    series = [math.exp(-mean)]
    for event_count in range(1, max_events + 1):
        series.append(series[-1] * mean / event_count)
    return series


def poisson_score_limit(mean: float) -> int:
    return max(POISSON_SCORE_MAX, int(math.ceil(mean + (6 * math.sqrt(mean + 1.0)))))


def poisson_cdf(mean: float, max_value: int) -> float:
    if max_value < 0:
        return 0.0
    return float(sum(poisson_probability_series(mean, max_value)))


def poisson_probability_over(mean: float, threshold: float) -> float:
    minimum = int(math.floor(threshold))
    return max(0.0, min(1.0, 1.0 - poisson_cdf(mean, minimum)))


def build_top_scores(home_mean: float, away_mean: float) -> list[tuple[str, int]]:
    max_goals = max(poisson_score_limit(home_mean), poisson_score_limit(away_mean))
    home_probs = poisson_probability_series(home_mean, max_goals)
    away_probs = poisson_probability_series(away_mean, max_goals)
    score_probs: list[tuple[str, float]] = []
    for home_goals, home_prob in enumerate(home_probs):
        for away_goals, away_prob in enumerate(away_probs):
            score_probs.append((f"{home_goals}-{away_goals}", home_prob * away_prob))
    score_probs.sort(key=lambda item: item[1], reverse=True)
    return [(score, int(round(probability * SIMULACIONES))) for score, probability in score_probs[:3]]


def simulate_match(xg_local: float, xg_visitante: float, xc_local: float, xc_visitante: float, xt_local: float, xt_visitante: float, xs_local: float, xs_visitante: float, xst_local: float, xst_visitante: float) -> dict:
    max_goals = max(poisson_score_limit(xg_local), poisson_score_limit(xg_visitante))
    home_goal_probs = poisson_probability_series(xg_local, max_goals)
    away_goal_probs = poisson_probability_series(xg_visitante, max_goals)
    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    for home_goals, home_prob in enumerate(home_goal_probs):
        for away_goals, away_prob in enumerate(away_goal_probs):
            joint_prob = home_prob * away_prob
            if home_goals > away_goals:
                home_win += joint_prob
            elif home_goals == away_goals:
                draw += joint_prob
            else:
                away_win += joint_prob

    goal_total_mean = xg_local + xg_visitante
    corner_total_mean = xc_local + xc_visitante
    top_scores = build_top_scores(xg_local, xg_visitante)
    return {
        "1": home_win,
        "X": draw,
        "2": away_win,
        "BTTS": (1.0 - math.exp(-xg_local)) * (1.0 - math.exp(-xg_visitante)),
        "O25": poisson_probability_over(goal_total_mean, 2.5),
        "U25": poisson_cdf(goal_total_mean, 2),
        "Home_Over15": poisson_probability_over(xg_local, 1.5),
        "Away_Over15": poisson_probability_over(xg_visitante, 1.5),
        "Home_CleanSheet": math.exp(-xg_visitante),
        "Away_CleanSheet": math.exp(-xg_local),
        "Corn_Home": xc_local,
        "Corn_Away": xc_visitante,
        "Over9.5_Corn": poisson_probability_over(corner_total_mean, 9.5),
        "Cards_Home": xt_local,
        "Cards_Away": xt_visitante,
        "Total_Cards": xt_local + xt_visitante,
        "Shots_Home": xs_local,
        "Shots_Away": xs_visitante,
        "ShotsOnTarget_Home": min(xs_local, xst_local),
        "ShotsOnTarget_Away": min(xs_visitante, xst_visitante),
        "Home_Over35_Corn": poisson_probability_over(xc_local, 3.5),
        "Away_Over35_Corn": poisson_probability_over(xc_visitante, 3.5),
        "Home_Over45_Corn": poisson_probability_over(xc_local, 4.5),
        "Away_Over45_Corn": poisson_probability_over(xc_visitante, 4.5),
        "Total_Goals": goal_total_mean,
        "Total_Corners": corner_total_mean,
        "TopScores": top_scores,
        "Marcador": top_scores[0][0] if top_scores else "0-0",
    }


def build_markets(resultado: dict, local: str, visitante: str) -> list[dict]:
    return [{"nombre": f"Victoria {local}", "prob": resultado["1"]}, {"nombre": "Empate", "prob": resultado["X"]}, {"nombre": f"Victoria {visitante}", "prob": resultado["2"]}, {"nombre": "Ambos marcan", "prob": resultado["BTTS"]}, {"nombre": "Over 2.5 goles", "prob": resultado["O25"]}, {"nombre": "Over 9.5 corners", "prob": resultado["Over9.5_Corn"]}]


def is_home_knockout_bonus_applicable(league: str, match_date) -> bool:
    if league not in LIGAS_FASE_ELIMINATORIA:
        return False
    if league == "Copa del Rey":
        return True
    if match_date is None:
        return True
    return getattr(match_date, "month", 1) >= 2


def calculate_knockout_home_bonus(stats_local: dict, stats_visitante: dict) -> tuple[float, float]:
    differential_ppg = max(0.0, stats_local["form"]["ppg"] - stats_visitante["form"]["ppg"])
    differential_win = max(0.0, stats_local["home"]["win_pct"] - stats_visitante["away"]["win_pct"])
    differential_gf = max(0.0, stats_local["home"]["gf"] - stats_visitante["away"]["gf"])
    differential_solidity = max(0.0, stats_local["home"]["clean_sheet_pct"] - stats_visitante["away"]["clean_sheet_pct"])
    local_bonus = 1 + min(0.22, (differential_ppg * 0.04) + (differential_win * 0.12) + (differential_gf * 0.03))
    away_penalty = min(0.14, (differential_win * 0.08) + (differential_solidity * 0.06))
    return local_bonus, away_penalty


def build_insights(analysis: dict) -> list[str]:
    resultado = analysis["resultado"]
    local_home = analysis["stats_local"]["home"]
    visitante_away = analysis["stats_visitante"]["away"]
    h2h = analysis["h2h"]
    insights = []
    if resultado["1"] > resultado["2"]:
        insights.append(f"El sesgo base favorece al local con {resultado['1'] * 100:.1f}% de victoria.")
    else:
        insights.append(f"El sesgo base favorece al visitante con {resultado['2'] * 100:.1f}% de victoria.")
    if local_home["gf"] > visitante_away["gc"]:
        insights.append(f"El ataque en casa de {analysis['local']} ({local_home['gf']:.2f}) supera la defensa fuera de {analysis['visitante']} ({visitante_away['gc']:.2f}).")
    if resultado["BTTS"] >= VALUE_BET_THRESHOLD:
        insights.append("Ambos marcan entra en zona caliente del modelo por encima del 65%.")
    if resultado["Over9.5_Corn"] >= 0.55:
        insights.append("El partido proyecta un volumen de corners alto y consistente con trading en vivo.")
    if h2h["matches"] == 0:
        insights.append(f"Sin H2H disponible, el contexto se apoya en los ultimos {analysis['stats_local']['comparison_window']} partidos generales.")
    return insights[:4]


def calculate_contextual_h2h_adjustment(stats_local: dict, stats_visitante: dict, h2h: dict) -> tuple[float, dict]:
    context_window = min(stats_local.get("comparison_window", 8), stats_visitante.get("comparison_window", 8))
    local_form_context = stats_local["comparison_form"]["ppg"]
    away_form_context = stats_visitante["comparison_form"]["ppg"]
    recent_adjustment = max(-0.03, min(0.03, (local_form_context - away_form_context) * 0.025))
    if h2h["matches"] <= 0:
        return recent_adjustment, {"mode": "recent_only", "window": context_window, "h2h_factor": 0.0, "recent_factor": recent_adjustment}
    sample_weight = min(1.0, h2h["matches"] / 4)
    h2h_factor = (h2h["local_win_pct"] - h2h["away_win_pct"]) * 0.03 * sample_weight
    final_adjustment = max(-0.05, min(0.05, h2h_factor + (recent_adjustment * 0.5)))
    return final_adjustment, {"mode": "h2h_plus_recent", "window": context_window, "h2h_factor": h2h_factor, "recent_factor": recent_adjustment}


def build_traceability(stats_local: dict, stats_visitante: dict, h2h: dict, ataque_local: float, defensa_visitante: float, ataque_visitante: float, defensa_local: float, ajuste_forma: float, ajuste_h2h: float, detalle_h2h: dict, xg_local: float, xg_visitante: float) -> dict:
    return {
        "local_xg": {"components": [{"label": "GF local en casa", "value": stats_local["home"]["gf"], "weight": 0.45, "group": "Ataque local"}, {"label": "GF local global", "value": stats_local["overall"]["gf"], "weight": 0.20, "group": "Ataque local"}, {"label": "GF local recientes", "value": stats_local["gf_rec"], "weight": 0.35, "group": "Ataque local"}, {"label": "GC visitante fuera", "value": stats_visitante["away"]["gc"], "weight": 0.45, "group": "Defensa visitante"}, {"label": "GC visitante global", "value": stats_visitante["overall"]["gc"], "weight": 0.20, "group": "Defensa visitante"}, {"label": "GC visitante recientes", "value": stats_visitante["gc_rec"], "weight": 0.35, "group": "Defensa visitante"}], "base_attack": ataque_local, "base_defense": defensa_visitante, "home_boost": 1.10, "form_adjustment": ajuste_forma, "h2h_adjustment": ajuste_h2h, "final_xg": xg_local},
        "visitante_xg": {"components": [{"label": "GF visitante fuera", "value": stats_visitante["away"]["gf"], "weight": 0.45, "group": "Ataque visitante"}, {"label": "GF visitante global", "value": stats_visitante["overall"]["gf"], "weight": 0.20, "group": "Ataque visitante"}, {"label": "GF visitante recientes", "value": stats_visitante["gf_rec"], "weight": 0.35, "group": "Ataque visitante"}, {"label": "GC local en casa", "value": stats_local["home"]["gc"], "weight": 0.45, "group": "Defensa local"}, {"label": "GC local global", "value": stats_local["overall"]["gc"], "weight": 0.20, "group": "Defensa local"}, {"label": "GC local recientes", "value": stats_local["gc_rec"], "weight": 0.35, "group": "Defensa local"}], "base_attack": ataque_visitante, "base_defense": defensa_local, "home_boost": 1.00, "form_adjustment": ajuste_forma, "h2h_adjustment": ajuste_h2h, "final_xg": xg_visitante},
        "adjustments": {"form": {"local_ppg": stats_local["form"]["ppg"], "visitante_ppg": stats_visitante["form"]["ppg"], "factor": ajuste_forma}, "h2h": {"matches": h2h["matches"], "local_win_pct": h2h["local_win_pct"], "away_win_pct": h2h["away_win_pct"], "factor": ajuste_h2h, "mode": detalle_h2h["mode"], "window": detalle_h2h["window"], "h2h_factor": detalle_h2h["h2h_factor"], "recent_factor": detalle_h2h["recent_factor"]}},
    }


def build_fallback_h2h(historico: pd.DataFrame, local: str, visitante: str) -> tuple[dict, dict, dict]:
    local_key = clave_equipo(local)
    away_key = clave_equipo(visitante)
    h2h_history = historico[
        ((historico["HomeTeam"].map(clave_equipo) == local_key) & (historico["AwayTeam"].map(clave_equipo) == away_key))
        | ((historico["HomeTeam"].map(clave_equipo) == away_key) & (historico["AwayTeam"].map(clave_equipo) == local_key))
    ].copy()
    if h2h_history.empty:
        return calcular_stats(historico, local), calcular_stats(historico, visitante), calcular_h2h(historico, local, visitante, 8)
    return calcular_stats(h2h_history, local), calcular_stats(h2h_history, visitante), calcular_h2h(h2h_history, local, visitante, 8)


def build_match_analysis(df: pd.DataFrame, liga: str, local: str, visitante: str, match_date=None, match_label: str = "") -> dict | None:
    historico = extraer_historico(df)
    stats_local = calcular_stats(historico, local)
    stats_visitante = calcular_stats(historico, visitante)
    h2h = calcular_h2h(historico, local, visitante, 8)
    if stats_local["overall"]["pj"] == 0 or stats_visitante["overall"]["pj"] == 0:
        stats_local, stats_visitante, h2h = build_fallback_h2h(historico, local, visitante)
        if stats_local["overall"]["pj"] == 0 or stats_visitante["overall"]["pj"] == 0:
            return None
    ataque_local = (stats_local["home"]["gf"] * 0.45) + (stats_local["overall"]["gf"] * 0.20) + (stats_local["gf_rec"] * 0.35)
    defensa_visitante = (stats_visitante["away"]["gc"] * 0.45) + (stats_visitante["overall"]["gc"] * 0.20) + (stats_visitante["gc_rec"] * 0.35)
    ataque_visitante = (stats_visitante["away"]["gf"] * 0.45) + (stats_visitante["overall"]["gf"] * 0.20) + (stats_visitante["gf_rec"] * 0.35)
    defensa_local = (stats_local["home"]["gc"] * 0.45) + (stats_local["overall"]["gc"] * 0.20) + (stats_local["gc_rec"] * 0.35)
    ajuste_forma = max(-0.08, min(0.08, (stats_local["form"]["ppg"] - stats_visitante["form"]["ppg"]) * 0.04))
    ajuste_h2h, detalle_h2h = calculate_contextual_h2h_adjustment(stats_local, stats_visitante, h2h)
    xg_local = ((ataque_local + defensa_visitante) / 2) * 1.10 * (1 + ajuste_forma + ajuste_h2h)
    xg_visitante = ((ataque_visitante + defensa_local) / 2) * (1 - ajuste_forma - (ajuste_h2h / 2))
    bonus_eliminatoria_local = 1.0
    penalizacion_eliminatoria_visitante = 0.0
    if is_home_knockout_bonus_applicable(liga, match_date):
        bonus_eliminatoria_local, penalizacion_eliminatoria_visitante = calculate_knockout_home_bonus(stats_local, stats_visitante)
        xg_local *= bonus_eliminatoria_local
        xg_visitante *= 1 - penalizacion_eliminatoria_visitante
    xg_local = max(0.15, xg_local)
    xg_visitante = max(0.15, xg_visitante)
    xc_local = (model_value(stats_local["home"], "corners_for", "has_corners", DEFAULT_CORNERS_FOR) * 0.55 + model_value(stats_local["overall"], "corners_for", "has_corners", DEFAULT_CORNERS_FOR) * 0.15 + model_value(stats_visitante["away"], "corners_against", "has_corners", DEFAULT_CORNERS_AGAINST) * 0.30) * 1.10
    xc_visitante = (model_value(stats_visitante["away"], "corners_for", "has_corners", DEFAULT_CORNERS_FOR) * 0.55 + model_value(stats_visitante["overall"], "corners_for", "has_corners", DEFAULT_CORNERS_FOR) * 0.15 + model_value(stats_local["home"], "corners_against", "has_corners", DEFAULT_CORNERS_AGAINST) * 0.30)
    xt_local = (model_value(stats_local["home"], "cards_for", "has_cards", DEFAULT_CARDS_FOR) * 0.50 + model_value(stats_local["overall"], "cards_for", "has_cards", DEFAULT_CARDS_FOR) * 0.15 + model_value(stats_visitante["away"], "cards_against", "has_cards", DEFAULT_CARDS_AGAINST) * 0.35)
    xt_visitante = (model_value(stats_visitante["away"], "cards_for", "has_cards", DEFAULT_CARDS_FOR) * 0.50 + model_value(stats_visitante["overall"], "cards_for", "has_cards", DEFAULT_CARDS_FOR) * 0.15 + model_value(stats_local["home"], "cards_against", "has_cards", DEFAULT_CARDS_AGAINST) * 0.35)
    xs_local = (offensive_model_value(stats_local["home"], stats_visitante["away"], "shots_for", "shots_against", "has_shots", DEFAULT_SHOTS_FOR) * 0.55 + offensive_model_value(stats_local["recent_overall"], stats_visitante["recent_overall"], "shots_for", "shots_against", "has_shots", DEFAULT_SHOTS_FOR) * 0.45)
    xs_visitante = (offensive_model_value(stats_visitante["away"], stats_local["home"], "shots_for", "shots_against", "has_shots", DEFAULT_SHOTS_FOR) * 0.55 + offensive_model_value(stats_visitante["recent_overall"], stats_local["recent_overall"], "shots_for", "shots_against", "has_shots", DEFAULT_SHOTS_FOR) * 0.45)
    xst_local = min(xs_local, (offensive_model_value(stats_local["home"], stats_visitante["away"], "shots_on_target_for", "shots_on_target_against", "has_shots_on_target", DEFAULT_SHOTS_ON_TARGET_FOR) * 0.55 + offensive_model_value(stats_local["recent_overall"], stats_visitante["recent_overall"], "shots_on_target_for", "shots_on_target_against", "has_shots_on_target", DEFAULT_SHOTS_ON_TARGET_FOR) * 0.45))
    xst_visitante = min(xs_visitante, (offensive_model_value(stats_visitante["away"], stats_local["home"], "shots_on_target_for", "shots_on_target_against", "has_shots_on_target", DEFAULT_SHOTS_ON_TARGET_FOR) * 0.55 + offensive_model_value(stats_visitante["recent_overall"], stats_local["recent_overall"], "shots_on_target_for", "shots_on_target_against", "has_shots_on_target", DEFAULT_SHOTS_ON_TARGET_FOR) * 0.45))
    local_display = nombre_visual_equipo(local)
    visitante_display = nombre_visual_equipo(visitante)
    resultado = simulate_match(xg_local, xg_visitante, xc_local, xc_visitante, xt_local, xt_visitante, xs_local, xs_visitante, xst_local, xst_visitante)
    mercados = build_markets(resultado, local_display, visitante_display)
    return {"liga": liga, "local": local_display, "visitante": visitante_display, "local_raw": local, "visitante_raw": visitante, "match_date": match_date, "match_label": match_label, "resultado": resultado, "stats_local": stats_local, "stats_visitante": stats_visitante, "h2h": h2h, "xg_local": xg_local, "xg_visitante": xg_visitante, "xc_local": xc_local, "xc_visitante": xc_visitante, "xt_local": xt_local, "xt_visitante": xt_visitante, "bonus_eliminatoria_local": bonus_eliminatoria_local, "penalizacion_eliminatoria_visitante": penalizacion_eliminatoria_visitante, "mercados": mercados, "trace": build_traceability(stats_local, stats_visitante, h2h, ataque_local, defensa_visitante, ataque_visitante, defensa_local, ajuste_forma, ajuste_h2h, detalle_h2h, xg_local, xg_visitante), "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
