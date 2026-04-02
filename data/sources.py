from __future__ import annotations

import io
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from data.teams import nombre_visual_equipo, normalizar_nombre, resolver_nombre_equipo


URLS_LIGAS = {
    "Premier League": "https://www.football-data.co.uk/mmz4281/2526/E0.csv",
    "LaLiga": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "Segunda Division": "https://www.football-data.co.uk/mmz4281/2526/SP2.csv",
    "Serie A": "https://www.football-data.co.uk/mmz4281/2526/I1.csv",
    "Bundesliga": "https://www.football-data.co.uk/mmz4281/2526/D1.csv",
    "Ligue 1": "https://www.football-data.co.uk/mmz4281/2526/F1.csv",
    "Eredivisie": "https://www.football-data.co.uk/mmz4281/2526/N1.csv",
    "Portugal": "https://www.football-data.co.uk/mmz4281/2526/P1.csv",
}

ESPN_LEAGUE_IDS = {
    "Premier League": "eng.1",
    "LaLiga": "esp.1",
    "Segunda Division": "esp.2",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Eredivisie": "ned.1",
    "Portugal": "por.1",
}

LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_datos(url: str) -> pd.DataFrame | None:
    try:
        respuesta = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        respuesta.raise_for_status()
        df = pd.read_csv(io.StringIO(respuesta.content.decode("utf-8", errors="ignore")))
        if "Home" in df.columns and "HomeTeam" not in df.columns:
            df = df.rename(
                columns={"Home": "HomeTeam", "Away": "AwayTeam", "HG": "FTHG", "AG": "FTAG"}
            )
        if len(df) > 500:
            df = df.tail(400)
        return df
    except Exception:
        return None


def preparar_calendario(df: pd.DataFrame) -> pd.DataFrame:
    calendario = df.copy()
    if "Date" in calendario.columns:
        fechas = pd.to_datetime(calendario["Date"], dayfirst=True, errors="coerce")
        if fechas.isna().all():
            fechas = pd.to_datetime(calendario["Date"], errors="coerce")
        calendario["MatchDate"] = fechas.dt.date
    else:
        calendario["MatchDate"] = pd.NaT

    if "Time" in calendario.columns:
        horas = calendario["Time"].fillna("").astype(str).str.strip()
        horas = horas.where(horas != "", "")
    else:
        horas = pd.Series([""] * len(calendario))

    fecha_texto = pd.Series(
        [valor.strftime("%d/%m/%Y") if pd.notna(valor) else "Sin fecha" for valor in calendario["MatchDate"]]
    )
    hora_texto = horas.apply(lambda valor: f" {valor}" if valor else "")
    calendario["FixtureLabel"] = (
        fecha_texto
        + hora_texto
        + " | "
        + calendario["HomeTeam"].fillna("TBD")
        + " vs "
        + calendario["AwayTeam"].fillna("TBD")
    )
    return calendario


@st.cache_data(ttl=1800, show_spinner=False)
def descargar_fixture_espn(league_id: str, fecha_objetivo) -> pd.DataFrame:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"
    params = {"dates": fecha_objetivo.strftime("%Y%m%d"), "limit": 100}

    try:
        respuesta = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        respuesta.raise_for_status()
        payload = respuesta.json()
        eventos = payload.get("events", [])
    except Exception:
        return pd.DataFrame()

    filas = []
    for evento in eventos:
        competicion = (evento.get("competitions") or [{}])[0]
        competidores = competicion.get("competitors") or []
        home = next((item for item in competidores if item.get("homeAway") == "home"), None)
        away = next((item for item in competidores if item.get("homeAway") == "away"), None)
        if not home or not away:
            continue

        fecha_evento = datetime.fromisoformat(evento["date"].replace("Z", "+00:00")).astimezone(LOCAL_TIMEZONE)
        home_name = home.get("team", {}).get("displayName", "")
        away_name = away.get("team", {}).get("displayName", "")
        hora = fecha_evento.strftime("%H:%M")
        filas.append(
            {
                "EventId": str(evento.get("id", "")),
                "MatchDate": fecha_evento.date(),
                "Time": hora,
                "HomeTeamRaw": home_name,
                "AwayTeamRaw": away_name,
                "HomeTeam": home_name,
                "AwayTeam": away_name,
                "FixtureLabel": f"{fecha_evento.strftime('%d/%m/%Y')} {hora} | {home_name} vs {away_name}",
                "Source": "ESPN",
            }
        )
    return pd.DataFrame(filas)


@st.cache_data(ttl=300, show_spinner=False)
def descargar_resumen_espn(league_id: str, event_id: str) -> dict:
    if not league_id or not event_id:
        return {}
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/summary"
    params = {"event": event_id}
    try:
        respuesta = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        respuesta.raise_for_status()
        return respuesta.json()
    except Exception:
        return {}


def fusionar_calendarios(csv_df: pd.DataFrame, espn_df: pd.DataFrame, equipos_csv: list[str]) -> pd.DataFrame:
    frames = []
    if not csv_df.empty:
        csv_local = csv_df.copy()
        csv_local["Source"] = csv_local.get("Source", "CSV")
        csv_local["HomeTeamRaw"] = csv_local.get("HomeTeamRaw", csv_local["HomeTeam"])
        csv_local["AwayTeamRaw"] = csv_local.get("AwayTeamRaw", csv_local["AwayTeam"])
        frames.append(csv_local)

    if not espn_df.empty:
        espn_local = espn_df.copy()
        espn_local["HomeTeam"] = espn_local["HomeTeamRaw"].apply(lambda nombre: resolver_nombre_equipo(nombre, equipos_csv))
        espn_local["AwayTeam"] = espn_local["AwayTeamRaw"].apply(lambda nombre: resolver_nombre_equipo(nombre, equipos_csv))
        frames.append(espn_local)

    if not frames:
        return pd.DataFrame()

    combinado = pd.concat(frames, ignore_index=True)
    combinado["dedupe_key"] = combinado.apply(
        lambda fila: (
            str(fila.get("MatchDate")),
            normalizar_nombre(fila.get("HomeTeamRaw", fila.get("HomeTeam", ""))),
            normalizar_nombre(fila.get("AwayTeamRaw", fila.get("AwayTeam", ""))),
        ),
        axis=1,
    )
    prioridad = {"ESPN": 0, "CSV": 1}
    combinado["priority"] = combinado["Source"].map(prioridad).fillna(9)
    return (
        combinado.sort_values(["priority", "Time", "FixtureLabel"])
        .drop_duplicates(subset=["dedupe_key"], keep="first")
        .drop(columns=["dedupe_key", "priority"])
    )


def american_to_decimal(valor) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if numero == 0:
        return None
    if numero > 0:
        return 1 + (numero / 100)
    return 1 + (100 / abs(numero))


def a_decimal_seguro(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def extraer_contexto_mercado_espn(resumen: dict) -> dict:
    competicion = ((resumen.get("header", {}) or {}).get("competitions") or [{}])[0]
    odds_header = competicion.get("odds") or []
    odds_root = resumen.get("odds") or []
    odds_data = odds_header[0] if odds_header else (odds_root[0] if odds_root else {})
    pickcenter = resumen.get("pickcenter") or []
    home_odds = odds_data.get("homeTeamOdds") or {}
    away_odds = odds_data.get("awayTeamOdds") or {}
    draw_odds = odds_data.get("drawOdds") or {}

    return {
        "provider": ((odds_data.get("provider") or {}).get("name")) or "Sin proveedor",
        "details": odds_data.get("details") or "Mercado principal",
        "over_under": a_decimal_seguro(odds_data.get("overUnder")),
        "spread": a_decimal_seguro(odds_data.get("spread")),
        "home_ml": home_odds.get("moneyLine"),
        "away_ml": away_odds.get("moneyLine"),
        "draw_ml": draw_odds.get("moneyLine"),
        "home_decimal": american_to_decimal(home_odds.get("moneyLine")),
        "away_decimal": american_to_decimal(away_odds.get("moneyLine")),
        "draw_decimal": american_to_decimal(draw_odds.get("moneyLine")),
        "pickcenter": pickcenter[:3],
        "available": bool(odds_data),
    }


def extraer_detalles_forma_espn(resumen: dict) -> list[dict]:
    boxscore = resumen.get("boxscore") or {}
    form_entries = boxscore.get("form") or []
    detalles = []
    for entrada in form_entries:
        team = entrada.get("team") or {}
        detalles.append(
            {
                "team": nombre_visual_equipo(team.get("displayName") or team.get("shortDisplayName") or "Equipo"),
                "summary": entrada.get("displayValue") or entrada.get("summary") or "Sin resumen",
                "value": entrada.get("value"),
            }
        )
    return detalles


def extraer_head_to_head_espn(resumen: dict) -> list[str]:
    juegos = resumen.get("headToHeadGames") or []
    etiquetas = []
    for juego in juegos[:4]:
        competencia = (juego.get("competitions") or [{}])[0]
        competidores = competencia.get("competitors") or []
        local = next((item for item in competidores if item.get("homeAway") == "home"), {})
        visitante = next((item for item in competidores if item.get("homeAway") == "away"), {})
        etiquetas.append(
            f"{nombre_visual_equipo((local.get('team') or {}).get('displayName', 'Local'))} {local.get('score', '-')} - {visitante.get('score', '-')} {nombre_visual_equipo((visitante.get('team') or {}).get('displayName', 'Visitante'))}"
        )
    return etiquetas


def extraer_disponibilidad_espn(resumen: dict) -> dict:
    texto = json.dumps(resumen, ensure_ascii=True).lower()
    return {
        "lineups": any(token in texto for token in ["lineup", "formation", "startingxi", "starter", "substitutes"]),
        "injuries": any(token in texto for token in ["injur", "susp"]),
        "xg_shots": any(token in texto for token in ["expectedgoals", "\"xg\"", "shotmap"]),
    }


def construir_cuotas_automaticas(contexto_mercado: dict, local: str, visitante: str) -> dict[str, dict]:
    cuotas = {}
    if contexto_mercado.get("home_decimal"):
        cuotas[f"Victoria {local}"] = {
            "odds": contexto_mercado["home_decimal"],
            "provider": contexto_mercado.get("provider", "Feed abierto"),
            "source": "auto",
        }
    if contexto_mercado.get("draw_decimal"):
        cuotas["Empate"] = {
            "odds": contexto_mercado["draw_decimal"],
            "provider": contexto_mercado.get("provider", "Feed abierto"),
            "source": "auto",
        }
    if contexto_mercado.get("away_decimal"):
        cuotas[f"Victoria {visitante}"] = {
            "odds": contexto_mercado["away_decimal"],
            "provider": contexto_mercado.get("provider", "Feed abierto"),
            "source": "auto",
        }
    return cuotas
