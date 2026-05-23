from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.config.teams import clave_equipo, nombre_visual_equipo


VENTANA_RECIENTE_GENERAL = 10
VENTANA_CONTEXTO_COMPARACION = 8


def extraer_historico(df: pd.DataFrame) -> pd.DataFrame:
    historico = df.copy()
    if "FTHG" in historico.columns and "FTAG" in historico.columns:
        historico = historico[historico["FTHG"].notna() & historico["FTAG"].notna()].copy()
    return historico


def obtener_partidos_equipo(df: pd.DataFrame, equipo: str, n_partidos: int | None = None) -> pd.DataFrame:
    clave = clave_equipo(equipo)
    home_keys = df["HomeTeam"].map(clave_equipo) if "HomeTeam" in df.columns else pd.Series(dtype=str)
    away_keys = df["AwayTeam"].map(clave_equipo) if "AwayTeam" in df.columns else pd.Series(dtype=str)
    partidos = df[(home_keys == clave) | (away_keys == clave)].copy()
    if n_partidos is not None:
        partidos = partidos.tail(n_partidos)
    return partidos


def columnas_disponibles(df: pd.DataFrame, columnas: list[str]) -> bool:
    return all(columna in df.columns for columna in columnas)


def serie_nan(longitud: int, index=None) -> pd.Series:
    return pd.Series([np.nan] * longitud, index=index, dtype=float)


def numero_seguro(valor) -> float:
    if pd.isna(valor):
        return 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def resumir_serie_numerica(serie: pd.Series) -> tuple[float, bool]:
    serie_numerica = pd.to_numeric(serie, errors="coerce")
    disponible = bool(serie_numerica.notna().any())
    if disponible:
        return float(serie_numerica.mean()), True
    return 0.0, False


def calcular_segmento(df: pd.DataFrame, equipo: str, scope: str) -> dict:
    equipo_clave = clave_equipo(equipo)
    tiene_corners = columnas_disponibles(df, ["HC", "AC"])
    tiene_shots = columnas_disponibles(df, ["HS", "AS"])
    tiene_shots_puerta = columnas_disponibles(df, ["HST", "AST"])
    tiene_tarjetas = any(columna in df.columns for columna in ["HY", "AY", "HR", "AR"])

    if scope == "home":
        partidos = df[df["HomeTeam"].map(clave_equipo) == equipo_clave].copy()
        goles_favor = partidos["FTHG"]
        goles_contra = partidos["FTAG"]
        corners_favor = partidos["HC"] if tiene_corners else serie_nan(len(partidos), partidos.index)
        corners_contra = partidos["AC"] if tiene_corners else serie_nan(len(partidos), partidos.index)
        shots_favor = partidos["HS"] if tiene_shots else serie_nan(len(partidos), partidos.index)
        shots_contra = partidos["AS"] if tiene_shots else serie_nan(len(partidos), partidos.index)
        shots_on_target_favor = partidos["HST"] if tiene_shots_puerta else serie_nan(len(partidos), partidos.index)
        shots_on_target_contra = partidos["AST"] if tiene_shots_puerta else serie_nan(len(partidos), partidos.index)
        if tiene_tarjetas:
            cards_favor = (
                partidos.get("HY", serie_nan(len(partidos), partidos.index)).fillna(0)
                + partidos.get("HR", serie_nan(len(partidos), partidos.index)).fillna(0)
            )
            cards_contra = (
                partidos.get("AY", serie_nan(len(partidos), partidos.index)).fillna(0)
                + partidos.get("AR", serie_nan(len(partidos), partidos.index)).fillna(0)
            )
        else:
            cards_favor = serie_nan(len(partidos), partidos.index)
            cards_contra = serie_nan(len(partidos), partidos.index)
        victorias = partidos["FTHG"] > partidos["FTAG"]
        empates = partidos["FTHG"] == partidos["FTAG"]
        derrotas = partidos["FTHG"] < partidos["FTAG"]
    elif scope == "away":
        partidos = df[df["AwayTeam"].map(clave_equipo) == equipo_clave].copy()
        goles_favor = partidos["FTAG"]
        goles_contra = partidos["FTHG"]
        corners_favor = partidos["AC"] if tiene_corners else serie_nan(len(partidos), partidos.index)
        corners_contra = partidos["HC"] if tiene_corners else serie_nan(len(partidos), partidos.index)
        shots_favor = partidos["AS"] if tiene_shots else serie_nan(len(partidos), partidos.index)
        shots_contra = partidos["HS"] if tiene_shots else serie_nan(len(partidos), partidos.index)
        shots_on_target_favor = partidos["AST"] if tiene_shots_puerta else serie_nan(len(partidos), partidos.index)
        shots_on_target_contra = partidos["HST"] if tiene_shots_puerta else serie_nan(len(partidos), partidos.index)
        if tiene_tarjetas:
            cards_favor = (
                partidos.get("AY", serie_nan(len(partidos), partidos.index)).fillna(0)
                + partidos.get("AR", serie_nan(len(partidos), partidos.index)).fillna(0)
            )
            cards_contra = (
                partidos.get("HY", serie_nan(len(partidos), partidos.index)).fillna(0)
                + partidos.get("HR", serie_nan(len(partidos), partidos.index)).fillna(0)
            )
        else:
            cards_favor = serie_nan(len(partidos), partidos.index)
            cards_contra = serie_nan(len(partidos), partidos.index)
        victorias = partidos["FTAG"] > partidos["FTHG"]
        empates = partidos["FTAG"] == partidos["FTHG"]
        derrotas = partidos["FTAG"] < partidos["FTHG"]
    else:
        casa = df[df["HomeTeam"].map(clave_equipo) == equipo_clave].copy()
        fuera = df[df["AwayTeam"].map(clave_equipo) == equipo_clave].copy()
        partidos = pd.concat([casa, fuera], ignore_index=True)
        if partidos.empty:
            goles_favor = pd.Series(dtype=float)
            goles_contra = pd.Series(dtype=float)
            corners_favor = pd.Series(dtype=float)
            corners_contra = pd.Series(dtype=float)
            shots_favor = pd.Series(dtype=float)
            shots_contra = pd.Series(dtype=float)
            shots_on_target_favor = pd.Series(dtype=float)
            shots_on_target_contra = pd.Series(dtype=float)
            cards_favor = pd.Series(dtype=float)
            cards_contra = pd.Series(dtype=float)
            victorias = pd.Series(dtype=bool)
            empates = pd.Series(dtype=bool)
            derrotas = pd.Series(dtype=bool)
        else:
            goles_favor = pd.Series([fila["FTHG"] if clave_equipo(fila["HomeTeam"]) == equipo_clave else fila["FTAG"] for _, fila in partidos.iterrows()])
            goles_contra = pd.Series([fila["FTAG"] if clave_equipo(fila["HomeTeam"]) == equipo_clave else fila["FTHG"] for _, fila in partidos.iterrows()])
            if tiene_corners:
                corners_favor = pd.Series([fila["HC"] if clave_equipo(fila["HomeTeam"]) == equipo_clave else fila["AC"] for _, fila in partidos.iterrows()])
                corners_contra = pd.Series([fila["AC"] if clave_equipo(fila["HomeTeam"]) == equipo_clave else fila["HC"] for _, fila in partidos.iterrows()])
            else:
                corners_favor = serie_nan(len(partidos))
                corners_contra = serie_nan(len(partidos))
            if tiene_shots:
                shots_favor = pd.Series([fila["HS"] if clave_equipo(fila["HomeTeam"]) == equipo_clave else fila["AS"] for _, fila in partidos.iterrows()])
                shots_contra = pd.Series([fila["AS"] if clave_equipo(fila["HomeTeam"]) == equipo_clave else fila["HS"] for _, fila in partidos.iterrows()])
            else:
                shots_favor = serie_nan(len(partidos))
                shots_contra = serie_nan(len(partidos))
            if tiene_shots_puerta:
                shots_on_target_favor = pd.Series([fila["HST"] if clave_equipo(fila["HomeTeam"]) == equipo_clave else fila["AST"] for _, fila in partidos.iterrows()])
                shots_on_target_contra = pd.Series([fila["AST"] if clave_equipo(fila["HomeTeam"]) == equipo_clave else fila["HST"] for _, fila in partidos.iterrows()])
            else:
                shots_on_target_favor = serie_nan(len(partidos))
                shots_on_target_contra = serie_nan(len(partidos))
            if tiene_tarjetas:
                cards_favor = pd.Series(
                    [
                        (numero_seguro(fila.get("HY")) + numero_seguro(fila.get("HR")))
                        if clave_equipo(fila["HomeTeam"]) == equipo_clave
                        else (numero_seguro(fila.get("AY")) + numero_seguro(fila.get("AR")))
                        for _, fila in partidos.iterrows()
                    ]
                )
                cards_contra = pd.Series(
                    [
                        (numero_seguro(fila.get("AY")) + numero_seguro(fila.get("AR")))
                        if clave_equipo(fila["HomeTeam"]) == equipo_clave
                        else (numero_seguro(fila.get("HY")) + numero_seguro(fila.get("HR")))
                        for _, fila in partidos.iterrows()
                    ]
                )
            else:
                cards_favor = serie_nan(len(partidos))
                cards_contra = serie_nan(len(partidos))
            victorias = goles_favor > goles_contra
            empates = goles_favor == goles_contra
            derrotas = goles_favor < goles_contra

    pj = int(len(partidos))
    if pj == 0:
        return {"pj": 0, "gf": 0.0, "gc": 0.0, "corners_for": 0.0, "corners_against": 0.0, "shots_for": 0.0, "shots_against": 0.0, "shots_on_target_for": 0.0, "shots_on_target_against": 0.0, "cards_for": 0.0, "cards_against": 0.0, "win_pct": 0.0, "draw_pct": 0.0, "loss_pct": 0.0, "btts_pct": 0.0, "over25_pct": 0.0, "clean_sheet_pct": 0.0, "fail_score_pct": 0.0, "total_goals": 0.0, "has_corners": False, "has_shots": False, "has_shots_on_target": False, "has_cards": False}

    corners_for_value, has_corners_for = resumir_serie_numerica(corners_favor)
    corners_against_value, has_corners_against = resumir_serie_numerica(corners_contra)
    shots_for_value, has_shots_for = resumir_serie_numerica(shots_favor)
    shots_against_value, has_shots_against = resumir_serie_numerica(shots_contra)
    shots_target_for_value, has_shots_target_for = resumir_serie_numerica(shots_on_target_favor)
    shots_target_against_value, has_shots_target_against = resumir_serie_numerica(shots_on_target_contra)
    cards_for_value, has_cards_for = resumir_serie_numerica(cards_favor)
    cards_against_value, has_cards_against = resumir_serie_numerica(cards_contra)
    total_goals = goles_favor + goles_contra
    return {
        "pj": pj,
        "gf": float(goles_favor.mean()),
        "gc": float(goles_contra.mean()),
        "corners_for": corners_for_value,
        "corners_against": corners_against_value,
        "shots_for": shots_for_value,
        "shots_against": shots_against_value,
        "shots_on_target_for": shots_target_for_value,
        "shots_on_target_against": shots_target_against_value,
        "cards_for": cards_for_value,
        "cards_against": cards_against_value,
        "win_pct": float(victorias.mean()),
        "draw_pct": float(empates.mean()),
        "loss_pct": float(derrotas.mean()),
        "btts_pct": float(((goles_favor > 0) & (goles_contra > 0)).mean()),
        "over25_pct": float((total_goals > 2.5).mean()),
        "clean_sheet_pct": float((goles_contra == 0).mean()),
        "fail_score_pct": float((goles_favor == 0).mean()),
        "total_goals": float(total_goals.mean()),
        "has_corners": has_corners_for or has_corners_against,
        "has_shots": has_shots_for or has_shots_against,
        "has_shots_on_target": has_shots_target_for or has_shots_target_against,
        "has_cards": has_cards_for or has_cards_against,
    }


def calcular_forma(df: pd.DataFrame, equipo: str, n_partidos: int = 8) -> dict:
    equipo_clave = clave_equipo(equipo)
    partidos = obtener_partidos_equipo(df, equipo, n_partidos)
    if partidos.empty:
        return {"matches": 0, "wins": 0, "draws": 0, "losses": 0, "points": 0, "ppg": 0.0, "goal_diff": 0, "results": [], "streak": "Sin datos"}

    resultados = []
    wins = draws = losses = 0
    goal_diff = 0
    for _, fila in partidos.iterrows():
        es_local = clave_equipo(fila["HomeTeam"]) == equipo_clave
        gf = fila["FTHG"] if es_local else fila["FTAG"]
        gc = fila["FTAG"] if es_local else fila["FTHG"]
        goal_diff += int(gf - gc)
        if gf > gc:
            resultados.append("W")
            wins += 1
        elif gf == gc:
            resultados.append("D")
            draws += 1
        else:
            resultados.append("L")
            losses += 1
    puntos = wins * 3 + draws
    return {"matches": len(partidos), "wins": wins, "draws": draws, "losses": losses, "points": puntos, "ppg": puntos / len(partidos), "goal_diff": goal_diff, "results": resultados, "streak": "-".join(resultados)}


def calcular_contexto_reciente(df: pd.DataFrame, equipo: str, n_partidos: int) -> dict:
    partidos = obtener_partidos_equipo(df, equipo, n_partidos)
    return {"window": n_partidos, "stats": calcular_segmento(partidos, equipo, "all"), "form": calcular_forma(df, equipo, n_partidos)}


def calcular_stats(df: pd.DataFrame, equipo: str) -> dict:
    todos = calcular_segmento(df, equipo, "all")
    casa = calcular_segmento(df, equipo, "home")
    fuera = calcular_segmento(df, equipo, "away")
    recientes = calcular_contexto_reciente(df, equipo, VENTANA_RECIENTE_GENERAL)
    comparacion = calcular_contexto_reciente(df, equipo, VENTANA_CONTEXTO_COMPARACION)
    stats_recientes = recientes["stats"] if recientes["stats"]["pj"] > 0 else todos
    return {
        "overall": todos,
        "home": casa,
        "away": fuera,
        "recent_window": recientes["window"],
        "recent_overall": stats_recientes,
        "comparison_window": comparacion["window"],
        "comparison_overall": comparacion["stats"] if comparacion["stats"]["pj"] > 0 else stats_recientes,
        "gf_rec": stats_recientes["gf"],
        "gc_rec": stats_recientes["gc"],
        "shots_rec": stats_recientes["shots_for"],
        "shots_on_target_rec": stats_recientes["shots_on_target_for"],
        "form": recientes["form"],
        "comparison_form": comparacion["form"],
    }


def valor_partido(fila: pd.Series, columna: str) -> float | None:
    if columna not in fila.index:
        return None
    valor = fila.get(columna)
    if pd.isna(valor):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def calcular_h2h(df: pd.DataFrame, local: str, visitante: str, limite: int = 6) -> dict:
    local_clave = clave_equipo(local)
    visitante_clave = clave_equipo(visitante)
    cruces = df[
        ((df["HomeTeam"].map(clave_equipo) == local_clave) & (df["AwayTeam"].map(clave_equipo) == visitante_clave))
        | ((df["HomeTeam"].map(clave_equipo) == visitante_clave) & (df["AwayTeam"].map(clave_equipo) == local_clave))
    ].copy().tail(limite)
    if cruces.empty:
        return {"matches": 0, "local_wins": 0, "away_wins": 0, "draws": 0, "local_win_pct": 0.0, "away_win_pct": 0.0, "avg_total_goals": 0.0, "btts_pct": 0.0, "over25_pct": 0.0, "recent_labels": [], "recent_matches": []}

    local_wins = away_wins = draws = 0
    etiquetas = []
    total_goals = []
    btts = []
    over25 = []
    partidos_detalle = []
    for indice, fila in cruces.iterrows():
        h2h_local = clave_equipo(fila["HomeTeam"]) == local_clave
        goles_local = fila["FTHG"] if h2h_local else fila["FTAG"]
        goles_visitante = fila["FTAG"] if h2h_local else fila["FTHG"]
        total = goles_local + goles_visitante
        total_goals.append(total)
        btts.append(goles_local > 0 and goles_visitante > 0)
        over25.append(total > 2.5)
        local_visual = nombre_visual_equipo(local)
        visitante_visual = nombre_visual_equipo(visitante)
        etiquetas.append(f"{local_visual} {int(goles_local)}-{int(goles_visitante)} {visitante_visual}")
        fecha_partido = pd.to_datetime(fila.get("Date"), dayfirst=True, errors="coerce")
        if pd.isna(fecha_partido):
            fecha_partido = pd.to_datetime(fila.get("Date"), errors="coerce")
        fecha_texto = fecha_partido.strftime("%d/%m/%Y") if pd.notna(fecha_partido) else "Sin fecha"
        home_team = nombre_visual_equipo(fila["HomeTeam"])
        away_team = nombre_visual_equipo(fila["AwayTeam"])
        winner_raw = fila["HomeTeam"] if fila["FTHG"] > fila["FTAG"] else (fila["AwayTeam"] if fila["FTAG"] > fila["FTHG"] else "Empate")
        partidos_detalle.append({"id": f"h2h_{indice}_{fila['HomeTeam']}_{fila['AwayTeam']}".lower().replace(" ", "_"), "date": fecha_texto, "home_team": home_team, "away_team": away_team, "home_score": int(fila["FTHG"]), "away_score": int(fila["FTAG"]), "label": f"{home_team} {int(fila['FTHG'])}-{int(fila['FTAG'])} {away_team}", "winner": nombre_visual_equipo(winner_raw) if winner_raw != "Empate" else "Empate", "btts": bool(fila["FTHG"] > 0 and fila["FTAG"] > 0), "over25": bool((fila["FTHG"] + fila["FTAG"]) > 2.5), "corners_home": valor_partido(fila, "HC"), "corners_away": valor_partido(fila, "AC"), "shots_home": valor_partido(fila, "HS"), "shots_away": valor_partido(fila, "AS"), "shots_on_target_home": valor_partido(fila, "HST"), "shots_on_target_away": valor_partido(fila, "AST"), "yellow_home": valor_partido(fila, "HY"), "yellow_away": valor_partido(fila, "AY"), "red_home": valor_partido(fila, "HR"), "red_away": valor_partido(fila, "AR"), "odds_home": valor_partido(fila, "B365H"), "odds_draw": valor_partido(fila, "B365D"), "odds_away": valor_partido(fila, "B365A")})
        if goles_local > goles_visitante:
            local_wins += 1
        elif goles_local < goles_visitante:
            away_wins += 1
        else:
            draws += 1

    partidos = len(cruces)
    return {"matches": partidos, "local_wins": local_wins, "away_wins": away_wins, "draws": draws, "local_win_pct": local_wins / partidos, "away_win_pct": away_wins / partidos, "avg_total_goals": float(np.mean(total_goals)), "btts_pct": float(np.mean(btts)), "over25_pct": float(np.mean(over25)), "recent_labels": etiquetas[::-1], "recent_matches": partidos_detalle[::-1]}
