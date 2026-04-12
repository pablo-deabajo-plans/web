from __future__ import annotations

import io
import json
import re
from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from data.teams import nombre_visual_equipo, normalizar_nombre, resolver_nombre_equipo

LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}


LEAGUE_CONFIGS = {
    "Premier League": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/E0.csv"},
        "espn_id": "eng.1",
    },
    "League One": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/E2.csv"},
        "espn_id": "eng.3",
    },
    "League Two": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/E3.csv"},
        "espn_id": "eng.4",
    },
    "Escocia Premiership": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SC0.csv"},
        "espn_id": "sco.1",
    },
    "Escocia Championship": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SC1.csv"},
        "espn_id": "sco.2",
    },
    "Escocia League One": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SC2.csv"},
        "espn_id": "sco.3",
    },
    "Escocia League Two": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SC3.csv"},
        "espn_id": "sco.4",
    },
    "Eliteserien": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/NOR.csv"},
        "espn_id": "",
    },
    "Allsvenskan": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/SWE.csv"},
        "espn_id": "",
    },
    "Superliga Dinamarca": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/DNK.csv"},
        "espn_id": "",
    },
    "LaLiga": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"},
        "espn_id": "esp.1",
    },
    "Segunda Division": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SP2.csv"},
        "espn_id": "esp.2",
    },
    "Serie A": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/I1.csv"},
        "espn_id": "ita.1",
    },
    "Serie B": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/I2.csv"},
        "espn_id": "ita.2",
    },
    "Bundesliga": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/D1.csv"},
        "espn_id": "ger.1",
    },
    "Ligue 1": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/F1.csv"},
        "espn_id": "fra.1",
    },
    "Ligue 2": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/F2.csv"},
        "espn_id": "fra.2",
    },
    "Holanda": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/N1.csv"},
        "espn_id": "ned.1",
    },
    "Belgica": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/B1.csv"},
        "espn_id": "bel.1",
    },
    "Liga de Portugal": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/P1.csv"},
        "espn_id": "por.1",
    },
    "Liga Portugal 2": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/P2.csv"},
        "espn_id": "",
    },
    "Super League Suiza": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/SWZ.csv"},
        "espn_id": "",
    },
    "Bundesliga Austria": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/AUT.csv"},
        "espn_id": "",
    },
    "Grecia": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/G1.csv"},
        "espn_id": "gre.1",
    },
    "Ekstraklasa": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/POL.csv"},
        "espn_id": "",
    },
    "Champions League": {
        "history": {"type": "espn_scoreboard", "league_id": "uefa.champions", "season": "european"},
        "espn_id": "uefa.champions",
    },
    "Europa League": {
        "history": {"type": "espn_scoreboard", "league_id": "uefa.europa", "season": "european"},
        "espn_id": "uefa.europa",
    },
    "Conference League": {
        "history": {"type": "espn_scoreboard", "league_id": "uefa.europa.conf", "season": "european"},
        "espn_id": "uefa.europa.conf",
    },
    "Copa del Rey": {
        "history": {"type": "espn_scoreboard", "league_id": "esp.copa_del_rey", "season": "european"},
        "espn_id": "esp.copa_del_rey",
    },
    "Turquia": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/T1.csv"},
        "espn_id": "tur.1",
    },
    "Segunda Inglesa": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/E1.csv"},
        "espn_id": "eng.2",
    },
    "Arabia Saudi": {
        "history": {"type": "espn_scoreboard", "league_id": "ksa.1", "season": "european"},
        "espn_id": "ksa.1",
    },
    "Australia": {
        "history": {"type": "espn_scoreboard", "league_id": "aus.1", "season": "australia"},
        "espn_id": "aus.1",
    },
    "Internacionales": {
        "history": {"type": "espn_scoreboard", "league_id": "fifa.friendly", "season": "calendar"},
        "espn_id": "fifa.friendly",
    },
    "Segunda Alemana": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/D2.csv"},
        "espn_id": "ger.2",
    },
    "Chile": {
        "history": {"type": "espn_scoreboard", "league_id": "chi.1", "season": "calendar"},
        "espn_id": "chi.1",
    },
    "MLS": {
        "history": {"type": "espn_scoreboard", "league_id": "usa.1", "season": "calendar"},
        "espn_id": "usa.1",
    },
    "Brasil": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/BRA.csv"},
        "espn_id": "",
    },
    "Serie B Brasil": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/BRA2.csv"},
        "espn_id": "",
    },
    "Primera B Nacional": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/ARG2.csv"},
        "espn_id": "",
    },
    "Liga MX": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/MEX.csv"},
        "espn_id": "",
    },
    "Primera A Colombia": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/COL.csv"},
        "espn_id": "",
    },
    "J1 League": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/JPN.csv"},
        "espn_id": "",
    },
    "J2 League": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/JPN2.csv"},
        "espn_id": "",
    },
    "K League 1": {
        "history": {"type": "football_data", "url": "https://www.football-data.co.uk/new/KOR.csv"},
        "espn_id": "",
    },
    "WSL Femenina": {
        "history": {"type": "espn_scoreboard", "league_id": "eng.w.1", "season": "european"},
        "espn_id": "eng.w.1",
    },
    "Liga F": {
        "history": {"type": "espn_scoreboard", "league_id": "esp.w.1", "season": "european"},
        "espn_id": "esp.w.1",
    },
    "Premiere Ligue Femenina": {
        "history": {"type": "espn_scoreboard", "league_id": "fra.w.1", "season": "european"},
        "espn_id": "fra.w.1",
    },
    "Frauen-Bundesliga": {
        "history": {"type": "footystats_fixtures", "url": "https://footystats.org/germany/frauen-bundesliga/fixtures"},
        "espn_id": "",
    },
    "Serie A Femenina": {
        "history": {"type": "footystats_fixtures", "url": "https://footystats.org/italy/serie-a-women/fixtures"},
        "espn_id": "",
    },
}

LEAGUE_COUNTRIES = {
    "Premier League": "Inglaterra",
    "League One": "Inglaterra",
    "League Two": "Inglaterra",
    "Escocia Premiership": "Escocia",
    "Escocia Championship": "Escocia",
    "Escocia League One": "Escocia",
    "Escocia League Two": "Escocia",
    "Eliteserien": "Noruega",
    "Allsvenskan": "Suecia",
    "Superliga Dinamarca": "Dinamarca",
    "LaLiga": "Espana",
    "Segunda Division": "Espana",
    "Serie A": "Italia",
    "Serie B": "Italia",
    "Bundesliga": "Alemania",
    "Ligue 1": "Francia",
    "Ligue 2": "Francia",
    "Holanda": "Paises Bajos",
    "Belgica": "Belgica",
    "Liga de Portugal": "Portugal",
    "Liga Portugal 2": "Portugal",
    "Super League Suiza": "Suiza",
    "Bundesliga Austria": "Austria",
    "Grecia": "Grecia",
    "Ekstraklasa": "Polonia",
    "Champions League": "Europa",
    "Europa League": "Europa",
    "Conference League": "Europa",
    "Copa del Rey": "Espana",
    "Turquia": "Turquia",
    "Segunda Inglesa": "Inglaterra",
    "Arabia Saudi": "Arabia Saudi",
    "Australia": "Australia",
    "Internacionales": "Internacional",
    "Segunda Alemana": "Alemania",
    "Chile": "Chile",
    "MLS": "Estados Unidos",
    "Brasil": "Brasil",
    "Serie B Brasil": "Brasil",
    "Primera B Nacional": "Argentina",
    "Liga MX": "Mexico",
    "Primera A Colombia": "Colombia",
    "J1 League": "Japon",
    "J2 League": "Japon",
    "K League 1": "Corea del Sur",
    "WSL Femenina": "Inglaterra",
    "Liga F": "Espana",
    "Premiere Ligue Femenina": "Francia",
    "Frauen-Bundesliga": "Alemania",
    "Serie A Femenina": "Italia",
}

URLS_LIGAS = {
    liga: config["history"].get("url", config["history"].get("league_id", ""))
    for liga, config in LEAGUE_CONFIGS.items()
}
ESPN_LEAGUE_IDS = {liga: config.get("espn_id", "") for liga, config in LEAGUE_CONFIGS.items()}


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_datos(url: str) -> pd.DataFrame | None:
    try:
        respuesta = requests.get(url, headers=HTTP_HEADERS, timeout=20)
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


def rango_temporada(tipo: str) -> tuple[str, str]:
    hoy = datetime.now(LOCAL_TIMEZONE).date()
    if tipo == "european":
        temporada_inicio = hoy.year if hoy.month >= 7 else hoy.year - 1
        inicio = datetime(temporada_inicio, 7, 1).date()
        fin = datetime(temporada_inicio + 1, 6, 30).date()
    elif tipo == "australia":
        temporada_inicio = hoy.year if hoy.month >= 7 else hoy.year - 1
        inicio = datetime(temporada_inicio, 7, 1).date()
        fin = datetime(temporada_inicio + 1, 5, 31).date()
    else:
        inicio = datetime(hoy.year, 1, 1).date()
        fin = datetime(hoy.year, 12, 31).date()
    return inicio.strftime("%Y%m%d"), fin.strftime("%Y%m%d")


def _fila_espn_evento(evento: dict, source: str) -> dict | None:
    competicion = (evento.get("competitions") or [{}])[0]
    competidores = competicion.get("competitors") or []
    home = next((item for item in competidores if item.get("homeAway") == "home"), None)
    away = next((item for item in competidores if item.get("homeAway") == "away"), None)
    if not home or not away:
        return None

    fecha_evento = datetime.fromisoformat(evento["date"].replace("Z", "+00:00")).astimezone(LOCAL_TIMEZONE)
    home_name = (home.get("team") or {}).get("displayName", "")
    away_name = (away.get("team") or {}).get("displayName", "")
    home_score = home.get("score")
    away_score = away.get("score")
    estado = (((competicion.get("status") or {}).get("type")) or {}).get("state", "")
    completado = bool((((competicion.get("status") or {}).get("type")) or {}).get("completed"))

    def extraer_stat_equipo(competidor: dict, claves: list[str]) -> float | None:
        estadisticas = competidor.get("statistics") or []
        for entrada in estadisticas:
            nombre = str((entrada or {}).get("name", "")).strip()
            abreviatura = str((entrada or {}).get("abbreviation", "")).strip()
            if nombre not in claves and abreviatura not in claves:
                continue
            valor = (entrada or {}).get("value", (entrada or {}).get("displayValue"))
            try:
                return float(valor)
            except (TypeError, ValueError):
                continue
        return None

    if completado or estado == "post":
        try:
            fthg = int(home_score) if str(home_score).strip() != "" else None
        except (TypeError, ValueError):
            fthg = None
        try:
            ftag = int(away_score) if str(away_score).strip() != "" else None
        except (TypeError, ValueError):
            ftag = None
    else:
        fthg = None
        ftag = None

    return {
        "EventId": str(evento.get("id", "")),
        "Date": fecha_evento.strftime("%d/%m/%Y"),
        "MatchDate": fecha_evento.date(),
        "Time": fecha_evento.strftime("%H:%M"),
        "HomeTeamRaw": home_name,
        "AwayTeamRaw": away_name,
        "HomeTeam": home_name,
        "AwayTeam": away_name,
        "FTHG": fthg,
        "FTAG": ftag,
        "HC": extraer_stat_equipo(home, ["wonCorners", "CW"]),
        "AC": extraer_stat_equipo(away, ["wonCorners", "CW"]),
        "HS": extraer_stat_equipo(home, ["totalShots", "SH"]),
        "AS": extraer_stat_equipo(away, ["totalShots", "SH"]),
        "HST": extraer_stat_equipo(home, ["shotsOnTarget", "ST"]),
        "AST": extraer_stat_equipo(away, ["shotsOnTarget", "ST"]),
        "FixtureLabel": f"{fecha_evento.strftime('%d/%m/%Y %H:%M')} | {home_name} vs {away_name}",
        "Source": source,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_historial_espn(league_id: str, season_type: str) -> pd.DataFrame | None:
    inicio, fin = rango_temporada(season_type)
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"
    params = {"dates": f"{inicio}-{fin}", "limit": 1000}

    try:
        respuesta = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=25)
        respuesta.raise_for_status()
        payload = respuesta.json()
    except Exception:
        return None

    filas = []
    for evento in payload.get("events", []):
        fila = _fila_espn_evento(evento, "HISTORY")
        if fila:
            filas.append(fila)

    if not filas:
        return pd.DataFrame()

    return pd.DataFrame(filas).sort_values(["MatchDate", "Time", "HomeTeam", "AwayTeam"]).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_fixture_footystats(url: str) -> pd.DataFrame | None:
    try:
        respuesta = requests.get(url, headers=HTTP_HEADERS, timeout=25)
        respuesta.raise_for_status()
        html = respuesta.text
    except Exception:
        return None

    bloques = re.findall(r"<ul class='match row cf [^']*'[^>]*>(.*?)</ul>", html, flags=re.S)
    filas = []
    for bloque in bloques:
        timestamp = re.search(r"data-time='(\d+)'", bloque)
        equipos = re.findall(
            r"class='team (home|away) fl'.*?<span[^>]*data-comp-id='[^']+'[^>]*>\s*([^<]+?)\s*</span>",
            bloque,
            flags=re.S,
        )
        if not timestamp or len(equipos) < 2:
            continue

        marcador = re.search(r"<span class='bold ft-score'>([^<]*)</span>", bloque)
        fecha_evento = datetime.fromtimestamp(int(timestamp.group(1)), tz=ZoneInfo("UTC")).astimezone(LOCAL_TIMEZONE)
        home_team = unescape(next((nombre for lado, nombre in equipos if lado == "home"), "").strip())
        away_team = unescape(next((nombre for lado, nombre in equipos if lado == "away"), "").strip())
        score_text = unescape(marcador.group(1).strip()) if marcador else ""
        score_match = re.match(r"(\d+)\s*-\s*(\d+)", score_text)
        fthg = int(score_match.group(1)) if score_match else None
        ftag = int(score_match.group(2)) if score_match else None

        filas.append(
            {
                "Date": fecha_evento.strftime("%d/%m/%Y"),
                "MatchDate": fecha_evento.date(),
                "Time": fecha_evento.strftime("%H:%M"),
                "HomeTeamRaw": home_team,
                "AwayTeamRaw": away_team,
                "HomeTeam": home_team,
                "AwayTeam": away_team,
                "FTHG": fthg,
                "FTAG": ftag,
                "FixtureLabel": f"{fecha_evento.strftime('%d/%m/%Y %H:%M')} | {home_team} vs {away_team}",
                "Source": "HISTORY",
            }
        )

    if not filas:
        return pd.DataFrame()

    return (
        pd.DataFrame(filas)
        .drop_duplicates(subset=["MatchDate", "Time", "HomeTeam", "AwayTeam"], keep="first")
        .sort_values(["MatchDate", "Time", "HomeTeam", "AwayTeam"])
        .reset_index(drop=True)
    )


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_datos_liga(liga: str) -> pd.DataFrame | None:
    config = LEAGUE_CONFIGS.get(liga, {})
    history = config.get("history", {})
    source_type = history.get("type")

    if source_type == "football_data":
        return descargar_datos(history["url"])
    if source_type == "espn_scoreboard":
        return descargar_historial_espn(history["league_id"], history.get("season", "calendar"))
    if source_type == "footystats_fixtures":
        return descargar_fixture_footystats(history["url"])
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
        respuesta = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=20)
        respuesta.raise_for_status()
        payload = respuesta.json()
    except Exception:
        return pd.DataFrame()

    filas = []
    for evento in payload.get("events", []):
        fila = _fila_espn_evento(evento, "ESPN")
        if fila:
            filas.append(fila)
    return pd.DataFrame(filas)


@st.cache_data(ttl=300, show_spinner=False)
def descargar_resumen_espn(league_id: str, event_id: str) -> dict:
    if not league_id or not event_id:
        return {}
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/summary"
    params = {"event": event_id}
    try:
        respuesta = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=20)
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
    prioridad = {"ESPN": 0, "HISTORY": 1, "CSV": 2}
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
