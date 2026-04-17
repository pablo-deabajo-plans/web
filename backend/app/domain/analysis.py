from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import numpy as np
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


def simulate_match(xg_local: float, xg_visitante: float, xc_local: float, xc_visitante: float, xt_local: float, xt_visitante: float, xs_local: float, xs_visitante: float, xst_local: float, xst_visitante: float) -> dict:
    goles_local = np.random.poisson(xg_local, SIMULACIONES)
    goles_visitante = np.random.poisson(xg_visitante, SIMULACIONES)
    corners_local = np.random.poisson(xc_local, SIMULACIONES)
    corners_visitante = np.random.poisson(xc_visitante, SIMULACIONES)
    cards_local = np.random.poisson(xt_local, SIMULACIONES)
    cards_visitante = np.random.poisson(xt_visitante, SIMULACIONES)
    shots_local = np.random.poisson(xs_local, SIMULACIONES)
    shots_visitante = np.random.poisson(xs_visitante, SIMULACIONES)
    shots_on_target_local = np.minimum(np.random.poisson(xst_local, SIMULACIONES), shots_local)
    shots_on_target_visitante = np.minimum(np.random.poisson(xst_visitante, SIMULACIONES), shots_visitante)
    marcadores = [f"{x}-{y}" for x, y in zip(goles_local, goles_visitante)]
    top_scores = Counter(marcadores).most_common(3)
    return {"1": float(np.mean(goles_local > goles_visitante)), "X": float(np.mean(goles_local == goles_visitante)), "2": float(np.mean(goles_local < goles_visitante)), "BTTS": float(np.mean((goles_local > 0) & (goles_visitante > 0))), "O25": float(np.mean((goles_local + goles_visitante) > 2.5)), "U25": float(np.mean((goles_local + goles_visitante) < 2.5)), "Home_Over15": float(np.mean(goles_local > 1.5)), "Away_Over15": float(np.mean(goles_visitante > 1.5)), "Home_CleanSheet": float(np.mean(goles_visitante == 0)), "Away_CleanSheet": float(np.mean(goles_local == 0)), "Corn_Home": float(np.mean(corners_local)), "Corn_Away": float(np.mean(corners_visitante)), "Over9.5_Corn": float(np.mean((corners_local + corners_visitante) > 9.5)), "Cards_Home": float(np.mean(cards_local)), "Cards_Away": float(np.mean(cards_visitante)), "Total_Cards": float(np.mean(cards_local + cards_visitante)), "Shots_Home": float(np.mean(shots_local)), "Shots_Away": float(np.mean(shots_visitante)), "ShotsOnTarget_Home": float(np.mean(shots_on_target_local)), "ShotsOnTarget_Away": float(np.mean(shots_on_target_visitante)), "Home_Over35_Corn": float(np.mean(corners_local > 3.5)), "Away_Over35_Corn": float(np.mean(corners_visitante > 3.5)), "Home_Over45_Corn": float(np.mean(corners_local > 4.5)), "Away_Over45_Corn": float(np.mean(corners_visitante > 4.5)), "Total_Goals": float(np.mean(goles_local + goles_visitante)), "Total_Corners": float(np.mean(corners_local + corners_visitante)), "TopScores": top_scores, "Marcador": top_scores[0][0] if top_scores else "0-0"}


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
