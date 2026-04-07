from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core.stats import calcular_h2h, calcular_stats, extraer_historico
from data.teams import nombre_visual_equipo


VALUE_BET_THRESHOLD = 0.65
SIMULACIONES = 50000
LIGAS_FASE_ELIMINATORIA = {
    "Champions League",
    "Europa League",
    "Conference League",
    "Copa del Rey",
}


def simular_partido(
    xg_local: float,
    xg_visitante: float,
    xc_local: float,
    xc_visitante: float,
    xt_local: float,
    xt_visitante: float,
) -> dict:
    goles_local = np.random.poisson(xg_local, SIMULACIONES)
    goles_visitante = np.random.poisson(xg_visitante, SIMULACIONES)
    corners_local = np.random.poisson(xc_local, SIMULACIONES)
    corners_visitante = np.random.poisson(xc_visitante, SIMULACIONES)
    cards_local = np.random.poisson(xt_local, SIMULACIONES)
    cards_visitante = np.random.poisson(xt_visitante, SIMULACIONES)
    marcadores = [f"{x}-{y}" for x, y in zip(goles_local, goles_visitante)]
    top_scores = Counter(marcadores).most_common(3)
    return {
        "1": float(np.mean(goles_local > goles_visitante)),
        "X": float(np.mean(goles_local == goles_visitante)),
        "2": float(np.mean(goles_local < goles_visitante)),
        "BTTS": float(np.mean((goles_local > 0) & (goles_visitante > 0))),
        "O25": float(np.mean((goles_local + goles_visitante) > 2.5)),
        "U25": float(np.mean((goles_local + goles_visitante) < 2.5)),
        "Home_Over15": float(np.mean(goles_local > 1.5)),
        "Away_Over15": float(np.mean(goles_visitante > 1.5)),
        "Home_CleanSheet": float(np.mean(goles_visitante == 0)),
        "Away_CleanSheet": float(np.mean(goles_local == 0)),
        "Corn_Home": float(np.mean(corners_local)),
        "Corn_Away": float(np.mean(corners_visitante)),
        "Over9.5_Corn": float(np.mean((corners_local + corners_visitante) > 9.5)),
        "Cards_Home": float(np.mean(cards_local)),
        "Cards_Away": float(np.mean(cards_visitante)),
        "Total_Cards": float(np.mean(cards_local + cards_visitante)),
        "Total_Goals": float(np.mean(goles_local + goles_visitante)),
        "Total_Corners": float(np.mean(corners_local + corners_visitante)),
        "TopScores": top_scores,
        "Marcador": top_scores[0][0] if top_scores else "0-0",
    }


def cuota_justa(probabilidad: float) -> float:
    if probabilidad <= 0:
        return 0.0
    return 1 / probabilidad


def stake_kelly(probabilidad: float, cuota_decimal: float) -> float:
    beneficio_neto = cuota_decimal - 1
    if beneficio_neto <= 0:
        return 0.0
    prob_perder = 1 - probabilidad
    valor = ((beneficio_neto * probabilidad) - prob_perder) / beneficio_neto
    return max(0.0, valor)


def construir_mercados(resultado: dict, local: str, visitante: str) -> list[dict]:
    return [
        {"nombre": f"Victoria {local}", "prob": resultado["1"]},
        {"nombre": "Empate", "prob": resultado["X"]},
        {"nombre": f"Victoria {visitante}", "prob": resultado["2"]},
        {"nombre": "Ambos marcan", "prob": resultado["BTTS"]},
        {"nombre": "Over 2.5 goles", "prob": resultado["O25"]},
        {"nombre": "Over 9.5 corners", "prob": resultado["Over9.5_Corn"]},
    ]


def es_fase_eliminatoria_casa(liga: str, match_date) -> bool:
    if liga not in LIGAS_FASE_ELIMINATORIA:
        return False
    if liga == "Copa del Rey":
        return True
    if match_date is None:
        return True
    return getattr(match_date, "month", 1) >= 2


def calcular_bonus_eliminatoria_casa(stats_local: dict, stats_visitante: dict) -> tuple[float, float]:
    diferencial_ppg = max(0.0, stats_local["form"]["ppg"] - stats_visitante["form"]["ppg"])
    diferencial_win = max(0.0, stats_local["home"]["win_pct"] - stats_visitante["away"]["win_pct"])
    diferencial_gf = max(0.0, stats_local["home"]["gf"] - stats_visitante["away"]["gf"])
    diferencial_solidez = max(0.0, stats_local["home"]["clean_sheet_pct"] - stats_visitante["away"]["clean_sheet_pct"])

    bonus_local = 1 + min(0.22, (diferencial_ppg * 0.04) + (diferencial_win * 0.12) + (diferencial_gf * 0.03))
    penalizacion_visitante = min(0.14, (diferencial_win * 0.08) + (diferencial_solidez * 0.06))
    return bonus_local, penalizacion_visitante


def construir_insights(analisis: dict) -> list[str]:
    resultado = analisis["resultado"]
    local_home = analisis["stats_local"]["home"]
    visitante_away = analisis["stats_visitante"]["away"]
    h2h = analisis["h2h"]
    insights = []
    if resultado["1"] > resultado["2"]:
        insights.append(f"El sesgo base favorece al local con {resultado['1'] * 100:.1f}% de victoria.")
    else:
        insights.append(f"El sesgo base favorece al visitante con {resultado['2'] * 100:.1f}% de victoria.")

    if local_home["gf"] > visitante_away["gc"]:
        insights.append(
            f"El ataque en casa de {analisis['local']} ({local_home['gf']:.2f}) supera la defensa fuera de {analisis['visitante']} ({visitante_away['gc']:.2f})."
        )
    if resultado["BTTS"] >= VALUE_BET_THRESHOLD:
        insights.append("Ambos marcan entra en zona caliente del modelo por encima del 65%.")
    if resultado["Over9.5_Corn"] >= 0.55:
        insights.append("El partido proyecta un volumen de corners alto y consistente con trading en vivo.")
    if h2h["matches"] == 0:
        insights.append(
            f"Sin H2H disponible, el contexto se apoya en los ultimos {analisis['stats_local']['comparison_window']} partidos generales."
        )
    return insights[:4]


def calcular_ajuste_h2h_contextual(stats_local: dict, stats_visitante: dict, h2h: dict) -> tuple[float, dict]:
    ventana_contexto = min(stats_local.get("comparison_window", 8), stats_visitante.get("comparison_window", 8))
    forma_local_contexto = stats_local["comparison_form"]["ppg"]
    forma_visitante_contexto = stats_visitante["comparison_form"]["ppg"]
    ajuste_reciente = max(-0.03, min(0.03, (forma_local_contexto - forma_visitante_contexto) * 0.025))

    if h2h["matches"] <= 0:
        return ajuste_reciente, {
            "mode": "recent_only",
            "window": ventana_contexto,
            "h2h_factor": 0.0,
            "recent_factor": ajuste_reciente,
        }

    peso_muestra_h2h = min(1.0, h2h["matches"] / 4)
    h2h_factor = (h2h["local_win_pct"] - h2h["away_win_pct"]) * 0.03 * peso_muestra_h2h
    ajuste_final = max(-0.05, min(0.05, h2h_factor + (ajuste_reciente * 0.5)))
    return ajuste_final, {
        "mode": "h2h_plus_recent",
        "window": ventana_contexto,
        "h2h_factor": h2h_factor,
        "recent_factor": ajuste_reciente,
    }


def construir_trazabilidad(
    stats_local: dict,
    stats_visitante: dict,
    h2h: dict,
    ataque_local: float,
    defensa_visitante: float,
    ataque_visitante: float,
    defensa_local: float,
    ajuste_forma: float,
    ajuste_h2h: float,
    detalle_h2h: dict,
    xg_local: float,
    xg_visitante: float,
) -> dict:
    return {
        "local_xg": {
            "components": [
                {"label": "GF local en casa", "value": stats_local["home"]["gf"], "weight": 0.45, "group": "Ataque local"},
                {"label": "GF local global", "value": stats_local["overall"]["gf"], "weight": 0.20, "group": "Ataque local"},
                {"label": "GF local recientes", "value": stats_local["gf_rec"], "weight": 0.35, "group": "Ataque local"},
                {"label": "GC visitante fuera", "value": stats_visitante["away"]["gc"], "weight": 0.45, "group": "Defensa visitante"},
                {"label": "GC visitante global", "value": stats_visitante["overall"]["gc"], "weight": 0.20, "group": "Defensa visitante"},
                {"label": "GC visitante recientes", "value": stats_visitante["gc_rec"], "weight": 0.35, "group": "Defensa visitante"},
            ],
            "base_attack": ataque_local,
            "base_defense": defensa_visitante,
            "home_boost": 1.10,
            "form_adjustment": ajuste_forma,
            "h2h_adjustment": ajuste_h2h,
            "final_xg": xg_local,
        },
        "visitante_xg": {
            "components": [
                {"label": "GF visitante fuera", "value": stats_visitante["away"]["gf"], "weight": 0.45, "group": "Ataque visitante"},
                {"label": "GF visitante global", "value": stats_visitante["overall"]["gf"], "weight": 0.20, "group": "Ataque visitante"},
                {"label": "GF visitante recientes", "value": stats_visitante["gf_rec"], "weight": 0.35, "group": "Ataque visitante"},
                {"label": "GC local en casa", "value": stats_local["home"]["gc"], "weight": 0.45, "group": "Defensa local"},
                {"label": "GC local global", "value": stats_local["overall"]["gc"], "weight": 0.20, "group": "Defensa local"},
                {"label": "GC local recientes", "value": stats_local["gc_rec"], "weight": 0.35, "group": "Defensa local"},
            ],
            "base_attack": ataque_visitante,
            "base_defense": defensa_local,
            "home_boost": 1.00,
            "form_adjustment": ajuste_forma,
            "h2h_adjustment": ajuste_h2h,
            "final_xg": xg_visitante,
        },
        "adjustments": {
            "form": {
                "local_ppg": stats_local["form"]["ppg"],
                "visitante_ppg": stats_visitante["form"]["ppg"],
                "factor": ajuste_forma,
            },
            "h2h": {
                "matches": h2h["matches"],
                "local_win_pct": h2h["local_win_pct"],
                "away_win_pct": h2h["away_win_pct"],
                "factor": ajuste_h2h,
                "mode": detalle_h2h["mode"],
                "window": detalle_h2h["window"],
                "h2h_factor": detalle_h2h["h2h_factor"],
                "recent_factor": detalle_h2h["recent_factor"],
            },
        },
    }


def construir_fallback_h2h(historico: pd.DataFrame, local: str, visitante: str) -> tuple[dict, dict, dict]:
    historico_h2h = historico[
        ((historico["HomeTeam"] == local) & (historico["AwayTeam"] == visitante))
        | ((historico["HomeTeam"] == visitante) & (historico["AwayTeam"] == local))
    ].copy()
    if historico_h2h.empty:
        return calcular_stats(historico, local), calcular_stats(historico, visitante), calcular_h2h(historico, local, visitante, 8)
    return (
        calcular_stats(historico_h2h, local),
        calcular_stats(historico_h2h, visitante),
        calcular_h2h(historico_h2h, local, visitante, 8),
    )


def guardar_analisis(df: pd.DataFrame, liga: str, local: str, visitante: str, match_date=None, match_label: str = "") -> dict | None:
    historico = extraer_historico(df)
    stats_local = calcular_stats(historico, local)
    stats_visitante = calcular_stats(historico, visitante)
    h2h = calcular_h2h(historico, local, visitante, 8)
    if stats_local["overall"]["pj"] == 0 or stats_visitante["overall"]["pj"] == 0:
        stats_local, stats_visitante, h2h = construir_fallback_h2h(historico, local, visitante)
        if stats_local["overall"]["pj"] == 0 or stats_visitante["overall"]["pj"] == 0:
            return None

    ataque_local = (
        stats_local["home"]["gf"] * 0.45
        + stats_local["overall"]["gf"] * 0.20
        + stats_local["gf_rec"] * 0.35
    )
    defensa_visitante = (
        stats_visitante["away"]["gc"] * 0.45
        + stats_visitante["overall"]["gc"] * 0.20
        + stats_visitante["gc_rec"] * 0.35
    )
    ataque_visitante = (
        stats_visitante["away"]["gf"] * 0.45
        + stats_visitante["overall"]["gf"] * 0.20
        + stats_visitante["gf_rec"] * 0.35
    )
    defensa_local = (
        stats_local["home"]["gc"] * 0.45
        + stats_local["overall"]["gc"] * 0.20
        + stats_local["gc_rec"] * 0.35
    )

    forma_local = stats_local["form"]["ppg"]
    forma_visitante = stats_visitante["form"]["ppg"]
    ajuste_forma = max(-0.08, min(0.08, (forma_local - forma_visitante) * 0.04))
    ajuste_h2h, detalle_h2h = calcular_ajuste_h2h_contextual(stats_local, stats_visitante, h2h)

    xg_local = ((ataque_local + defensa_visitante) / 2) * 1.10 * (1 + ajuste_forma + ajuste_h2h)
    xg_visitante = ((ataque_visitante + defensa_local) / 2) * (1 - ajuste_forma - (ajuste_h2h / 2))
    bonus_eliminatoria_local = 1.0
    penalizacion_eliminatoria_visitante = 0.0
    if es_fase_eliminatoria_casa(liga, match_date):
        bonus_eliminatoria_local, penalizacion_eliminatoria_visitante = calcular_bonus_eliminatoria_casa(stats_local, stats_visitante)
        xg_local *= bonus_eliminatoria_local
        xg_visitante *= 1 - penalizacion_eliminatoria_visitante
    xg_local = max(0.15, xg_local)
    xg_visitante = max(0.15, xg_visitante)

    xc_local = (
        stats_local["home"]["corners_for"] * 0.55
        + stats_local["overall"]["corners_for"] * 0.15
        + stats_visitante["away"]["corners_against"] * 0.30
    ) * 1.10
    xc_visitante = (
        stats_visitante["away"]["corners_for"] * 0.55
        + stats_visitante["overall"]["corners_for"] * 0.15
        + stats_local["home"]["corners_against"] * 0.30
    )
    xt_local = (
        stats_local["home"]["cards_for"] * 0.50
        + stats_local["overall"]["cards_for"] * 0.15
        + stats_visitante["away"]["cards_against"] * 0.35
    )
    xt_visitante = (
        stats_visitante["away"]["cards_for"] * 0.50
        + stats_visitante["overall"]["cards_for"] * 0.15
        + stats_local["home"]["cards_against"] * 0.35
    )

    local_display = nombre_visual_equipo(local)
    visitante_display = nombre_visual_equipo(visitante)
    resultado = simular_partido(xg_local, xg_visitante, xc_local, xc_visitante, xt_local, xt_visitante)
    mercados = construir_mercados(resultado, local_display, visitante_display)

    return {
        "liga": liga,
        "local": local_display,
        "visitante": visitante_display,
        "local_raw": local,
        "visitante_raw": visitante,
        "match_date": match_date,
        "match_label": match_label,
        "resultado": resultado,
        "stats_local": stats_local,
        "stats_visitante": stats_visitante,
        "h2h": h2h,
        "xg_local": xg_local,
        "xg_visitante": xg_visitante,
        "xc_local": xc_local,
        "xc_visitante": xc_visitante,
        "xt_local": xt_local,
        "xt_visitante": xt_visitante,
        "bonus_eliminatoria_local": bonus_eliminatoria_local,
        "penalizacion_eliminatoria_visitante": penalizacion_eliminatoria_visitante,
        "mercados": mercados,
        "trace": construir_trazabilidad(
            stats_local,
            stats_visitante,
            h2h,
            ataque_local,
            defensa_visitante,
            ataque_visitante,
            defensa_local,
            ajuste_forma,
            ajuste_h2h,
            detalle_h2h,
            xg_local,
            xg_visitante,
        ),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def construir_ranking_value_bets(items: list[dict], limite: int = 10) -> list[dict]:
    ranking = []
    for item in items:
        analisis = item.get("analysis")
        auto_odds = item.get("auto_odds") or {}
        if not analisis or not auto_odds:
            continue
        for mercado in analisis["mercados"]:
            if mercado["nombre"] not in auto_odds:
                continue
            cuota = auto_odds[mercado["nombre"]]["odds"]
            prob = mercado["prob"]
            fair_odds = cuota_justa(prob)
            edge = (prob * cuota) - 1
            ranking.append(
                {
                    "match": f"{analisis['local']} vs {analisis['visitante']}",
                    "market": mercado["nombre"],
                    "prob": prob,
                    "fair_odds": fair_odds,
                    "offered_odds": cuota,
                    "edge": edge,
                    "provider": auto_odds[mercado["nombre"]]["provider"],
                }
            )
    ranking.sort(key=lambda fila: fila["edge"], reverse=True)
    return ranking[:limite]
