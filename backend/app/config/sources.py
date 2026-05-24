from __future__ import annotations

import functools
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path

import pandas as pd
import httpx

from backend.app.core.cache import TTLCache

_SOURCES_CACHE = TTLCache()

try:
    import streamlit as st
except ModuleNotFoundError:
    class _StreamlitFallback:
        session_state: dict[str, str] = {}
        secrets: dict[str, str] = {}

        @staticmethod
        def cache_data(ttl: int = 3600, **__):
            def decorator(func):
                @functools.wraps(func)
                def wrapper(*args, **kwargs):
                    key = repr((args, sorted(kwargs.items())))
                    return _SOURCES_CACHE.get_or_set(func.__name__, key, ttl, lambda: func(*args, **kwargs))
                return wrapper
            return decorator

    st = _StreamlitFallback()

from backend.app.core.time import LOCAL_TIMEZONE, UTC, to_local_datetime, utc_dates_for_local_day
from backend.app.domain.leagues import LEAGUE_DEFINITIONS, LEAGUE_IDS
from backend.app.repositories.providers import (
    fetch_espn_matches_for_date,
    fetch_espn_matches_for_season,
    fetch_espn_scoreboard,
    fetch_espn_summary,
    fetch_sportmonks_paginated,
    fetch_sportmonks_resource,
)
from backend.app.repositories.providers.espn import ESPNProviderError, extract_supported_odds
from backend.app.config.teams import nombre_visual_equipo, normalizar_nombre, resolver_nombre_equipo

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
LOGGER = logging.getLogger(__name__)
SPORTMONKS_BASE_URL = "https://api.sportmonks.com/v3/football"
SPORTMONKS_PLAYER_STAT_TYPES = {
    "shots_total": 42,
    "fouls_committed": 56,
    "shots_on_target": 86,
    "fouls_drawn": 96,
    "minutes_played": 119,
}


HISTORY_SOURCE_CONFIGS: dict[str, dict[str, str]] = {
    "Premier League": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/E0.csv"},
    "League One": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/E2.csv"},
    "League Two": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/E3.csv"},
    "Escocia Premiership": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SC0.csv"},
    "Escocia Championship": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SC1.csv"},
    "Escocia League One": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SC2.csv"},
    "Escocia League Two": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SC3.csv"},
    "Eliteserien": {"type": "football_data", "url": "https://www.football-data.co.uk/new/NOR.csv"},
    "Allsvenskan": {"type": "football_data", "url": "https://www.football-data.co.uk/new/SWE.csv"},
    "Superliga Dinamarca": {"type": "football_data", "url": "https://www.football-data.co.uk/new/DNK.csv"},
    "LaLiga": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"},
    "Segunda Division": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/SP2.csv"},
    "Serie A": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/I1.csv"},
    "Serie B": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/I2.csv"},
    "Bundesliga": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/D1.csv"},
    "Ligue 1": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/F1.csv"},
    "Ligue 2": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/F2.csv"},
    "Holanda": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/N1.csv"},
    "Belgica": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/B1.csv"},
    "Liga de Portugal": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/P1.csv"},
    "Liga Portugal 2": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/P2.csv"},
    "Super League Suiza": {"type": "football_data", "url": "https://www.football-data.co.uk/new/SWZ.csv"},
    "Bundesliga Austria": {"type": "football_data", "url": "https://www.football-data.co.uk/new/AUT.csv"},
    "Grecia": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/G1.csv"},
    "Ekstraklasa": {"type": "football_data", "url": "https://www.football-data.co.uk/new/POL.csv"},
    "Champions League": {"type": "espn_scoreboard"},
    "Europa League": {"type": "espn_scoreboard"},
    "Conference League": {"type": "espn_scoreboard"},
    "Copa del Rey": {"type": "espn_scoreboard"},
    "Turquia": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/T1.csv"},
    "Segunda Inglesa": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/E1.csv"},
    "Arabia Saudi": {"type": "espn_scoreboard"},
    "Australia": {"type": "espn_scoreboard"},
    "Internacionales": {"type": "espn_scoreboard"},
    "Segunda Alemana": {"type": "football_data", "url": "https://www.football-data.co.uk/mmz4281/2526/D2.csv"},
    "Chile": {"type": "espn_scoreboard"},
    "MLS": {"type": "espn_scoreboard"},
    "Brasil": {"type": "football_data", "url": "https://www.football-data.co.uk/new/BRA.csv"},
    "Serie B Brasil": {"type": "football_data", "url": "https://www.football-data.co.uk/new/BRA2.csv"},
    "Primera B Nacional": {"type": "football_data", "url": "https://www.football-data.co.uk/new/ARG2.csv"},
    "Liga MX": {"type": "football_data", "url": "https://www.football-data.co.uk/new/MEX.csv"},
    "Primera A Colombia": {"type": "football_data", "url": "https://www.football-data.co.uk/new/COL.csv"},
    "J1 League": {"type": "football_data", "url": "https://www.football-data.co.uk/new/JPN.csv"},
    "J2 League": {"type": "football_data", "url": "https://www.football-data.co.uk/new/JPN2.csv"},
    "K League 1": {"type": "football_data", "url": "https://www.football-data.co.uk/new/KOR.csv"},
    "WSL Femenina": {"type": "espn_scoreboard"},
    "Liga F": {"type": "espn_scoreboard"},
    "Premiere Ligue Femenina": {"type": "espn_scoreboard"},
    "Frauen-Bundesliga": {"type": "footystats_fixtures", "url": "https://footystats.org/germany/frauen-bundesliga/fixtures"},
    "Serie A Femenina": {"type": "footystats_fixtures", "url": "https://footystats.org/italy/serie-a-women/fixtures"},
}


def _build_league_configs() -> dict[str, dict]:
    configs: dict[str, dict] = {}
    for league_name, definition in LEAGUE_DEFINITIONS.items():
        history = dict(HISTORY_SOURCE_CONFIGS.get(league_name, {}))
        if history.get("type") == "espn_scoreboard":
            history["league_id"] = definition.league_id
            history["season"] = definition.season_type

        configs[league_name] = {
            "country": definition.country,
            "league_id": definition.league_id,
            "season_type": definition.season_type,
            "history": history,
        }
    return configs


LEAGUE_CONFIGS = _build_league_configs()

URLS_LIGAS = {
    liga: config["history"].get("url", config["history"].get("league_id", ""))
    for liga, config in LEAGUE_CONFIGS.items()
}
ESPN_LEAGUE_IDS = dict(LEAGUE_IDS)


def _log_request_error(contexto: str, exc: Exception, extra: dict | None = None) -> None:
    payload = {
        "event": "source_request_failed",
        "context": contexto,
        "source": "data_sources",
        "league": None,
        "match_id": None,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    payload.update(extra or {})
    LOGGER.warning(json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _localize_espn_row(row: dict) -> dict:
    kickoff_at = row.get("KickoffAt")
    if not isinstance(kickoff_at, datetime):
        return dict(row)

    local_kickoff = to_local_datetime(kickoff_at)
    localized = dict(row)
    localized["KickoffAt"] = local_kickoff
    localized["Date"] = local_kickoff.strftime("%d/%m/%Y")
    localized["MatchDate"] = local_kickoff.date()
    localized["Time"] = local_kickoff.strftime("%H:%M")
    localized["FixtureLabel"] = (
        f"{local_kickoff.strftime('%d/%m/%Y %H:%M')} | "
        f"{localized.get('HomeTeamRaw', localized.get('HomeTeam', ''))} vs "
        f"{localized.get('AwayTeamRaw', localized.get('AwayTeam', ''))}"
    )
    return localized


def _load_localized_espn_rows_for_local_day(league_id: str, target_local_date, *, source: str, timeout: int) -> list[dict]:
    rows: list[dict] = []
    seen_event_ids: set[str] = set()
    for utc_date in utc_dates_for_local_day(target_local_date):
        batch = fetch_espn_matches_for_date(league_id, utc_date, source=source, timeout=timeout)
        for row in batch:
            localized = _localize_espn_row(row)
            if localized.get("MatchDate") != target_local_date:
                continue
            event_id = str(localized.get("EventId", "")).strip()
            dedupe_key = event_id or json.dumps(
                [
                    str(localized.get("MatchDate")),
                    localized.get("Time"),
                    localized.get("HomeTeam"),
                    localized.get("AwayTeam"),
                ],
                ensure_ascii=True,
            )
            if dedupe_key in seen_event_ids:
                continue
            seen_event_ids.add(dedupe_key)
            rows.append(localized)
    return rows


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_datos(url: str) -> pd.DataFrame | None:
    try:
        respuesta = httpx.get(url, headers=HTTP_HEADERS, timeout=20, follow_redirects=True)
        respuesta.raise_for_status()
        df = pd.read_csv(io.StringIO(respuesta.content.decode("utf-8", errors="ignore")))
        if "Home" in df.columns and "HomeTeam" not in df.columns:
            df = df.rename(
                columns={"Home": "HomeTeam", "Away": "AwayTeam", "HG": "FTHG", "AG": "FTAG"}
            )
        if len(df) > 500:
            df = df.tail(400)
        return df
    except (httpx.HTTPError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        _log_request_error("descargar_datos", exc, {"url": url})
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_historial_espn(league_id: str, season_type: str) -> pd.DataFrame | None:
    try:
        filas = fetch_espn_matches_for_season(league_id, season_type, source="HISTORY", timeout=25)
    except ESPNProviderError as exc:
        _log_request_error(
            "descargar_historial_espn",
            exc,
            {
                "source": "espn",
                "league": league_id,
                "league_id": league_id,
                "season_type": season_type,
            },
        )
        return None

    filas = [_localize_espn_row(fila) for fila in filas]
    if not filas:
        return pd.DataFrame()

    return pd.DataFrame(filas).sort_values(["MatchDate", "Time", "HomeTeam", "AwayTeam"]).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_fixture_footystats(url: str) -> pd.DataFrame | None:
    try:
        respuesta = httpx.get(url, headers=HTTP_HEADERS, timeout=25, follow_redirects=True)
        respuesta.raise_for_status()
        html = respuesta.text
    except httpx.HTTPError as exc:
        _log_request_error("descargar_fixture_footystats", exc, {"url": url})
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
        fecha_evento = datetime.fromtimestamp(int(timestamp.group(1)), tz=UTC).astimezone(LOCAL_TIMEZONE)
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


# Downloads run synchronously on first call per process; TTLCache (1 h) prevents repeats.
# Cache is in-memory only — cold restarts re-download. Persistent caching is deferred.
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
    try:
        filas = _load_localized_espn_rows_for_local_day(league_id, fecha_objetivo, source="ESPN", timeout=20)
    except ESPNProviderError as exc:
        _log_request_error(
            "descargar_fixture_espn",
            exc,
            {
                "source": "espn",
                "league": league_id,
                "league_id": league_id,
                "match_id": None,
                "fecha_objetivo": str(fecha_objetivo),
            },
        )
        return pd.DataFrame()

    return pd.DataFrame(filas)


@st.cache_data(ttl=300, show_spinner=False)
def descargar_resumen_espn(league_id: str, event_id: str) -> dict:
    if not league_id or not event_id:
        return {}
    return fetch_espn_summary(league_id, event_id, timeout=20)


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

    context = {
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
    for snapshot in extract_supported_odds(resumen):
        if snapshot["market"] == "BTTS" and snapshot["selection"] == "YES":
            context["btts_yes_decimal"] = snapshot["decimal_odds"]
        elif snapshot["market"] == "BTTS" and snapshot["selection"] == "NO":
            context["btts_no_decimal"] = snapshot["decimal_odds"]
        elif snapshot["market"] == "TOTAL_GOALS" and snapshot["selection"] == "OVER_2_5":
            context["over_2_5_decimal"] = snapshot["decimal_odds"]
        elif snapshot["market"] == "TOTAL_GOALS" and snapshot["selection"] == "UNDER_2_5":
            context["under_2_5_decimal"] = snapshot["decimal_odds"]
    return context


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
    if contexto_mercado.get("btts_yes_decimal"):
        cuotas["Ambos marcan"] = {
            "odds": contexto_mercado["btts_yes_decimal"],
            "provider": contexto_mercado.get("provider", "Feed abierto"),
            "source": "auto",
        }
    if contexto_mercado.get("btts_no_decimal"):
        cuotas["No marcan ambos"] = {
            "odds": contexto_mercado["btts_no_decimal"],
            "provider": contexto_mercado.get("provider", "Feed abierto"),
            "source": "auto",
        }
    if contexto_mercado.get("over_2_5_decimal"):
        cuotas["Over 2.5 goles"] = {
            "odds": contexto_mercado["over_2_5_decimal"],
            "provider": contexto_mercado.get("provider", "Feed abierto"),
            "source": "auto",
        }
    if contexto_mercado.get("under_2_5_decimal"):
        cuotas["Under 2.5 goles"] = {
            "odds": contexto_mercado["under_2_5_decimal"],
            "provider": contexto_mercado.get("provider", "Feed abierto"),
            "source": "auto",
        }
    return cuotas


def _sportmonks_token(token_hint: str = "") -> str:
    hinted = str(token_hint or "").strip()
    if hinted:
        return hinted

    token_session = str(st.session_state.get("sportmonks_api_token", "") or "").strip()
    if token_session:
        return token_session

    token_secret = str(st.secrets.get("SPORTMONKS_API_TOKEN", "") or "").strip()
    if token_secret:
        return token_secret

    secrets_path = Path(".streamlit") / "secrets.toml"
    if secrets_path.exists():
        try:
            contenido = secrets_path.read_text(encoding="utf-8")
            match = re.search(r'^\s*SPORTMONKS_API_TOKEN\s*=\s*["\']?([^"\']+)["\']?\s*$', contenido, re.MULTILINE)
            if match:
                token_file = match.group(1).strip()
                if token_file:
                    return token_file
        except OSError as exc:
            _log_request_error("_sportmonks_token", exc, {"path": str(secrets_path)})

    return os.getenv("SPORTMONKS_API_TOKEN", "").strip()


def _sportmonks_parse_float(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _sportmonks_parse_datetime(valor) -> datetime | None:
    if isinstance(valor, dict):
        for clave in ["date_time", "starting_at", "starting_at_timestamp", "date", "datetime"]:
            candidato = valor.get(clave)
            if candidato:
                return _sportmonks_parse_datetime(candidato)
        return None
    if isinstance(valor, (int, float)):
        try:
            return datetime.fromtimestamp(valor, tz=UTC).astimezone(LOCAL_TIMEZONE)
        except (OSError, OverflowError, ValueError):
            return None
    if not valor:
        return None
    texto = str(valor).strip().replace("Z", "+00:00")
    for candidato in [texto, texto.replace(" ", "T")]:
        try:
            fecha = datetime.fromisoformat(candidato)
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=UTC)
            return fecha.astimezone(LOCAL_TIMEZONE)
        except ValueError:
            continue
    return None


def _sportmonks_request(path: str, params: dict | None = None) -> dict:
    token = _sportmonks_token()
    if not token:
        return {}
    return fetch_sportmonks_resource(SPORTMONKS_BASE_URL, path, token, params=params, timeout=25)


def _sportmonks_paginated(path: str, params: dict | None = None, max_pages: int = 4) -> list[dict]:
    token = _sportmonks_token()
    if not token:
        return []
    return fetch_sportmonks_paginated(SPORTMONKS_BASE_URL, path, token, params=params, max_pages=max_pages)


def _sportmonks_participant_name(participant: dict) -> str:
    return (
        participant.get("name")
        or participant.get("short_name")
        or participant.get("display_name")
        or participant.get("common_name")
        or "Equipo"
    )


def _sportmonks_lineup_player_name(lineup: dict) -> str:
    jugador = lineup.get("player") or lineup.get("participant") or {}
    return (
        jugador.get("display_name")
        or jugador.get("common_name")
        or jugador.get("name")
        or lineup.get("player_name")
        or "Jugador"
    )


def _sportmonks_position_name(lineup: dict) -> str:
    posicion = lineup.get("detailedposition") or lineup.get("detailedPosition") or lineup.get("position") or {}
    return posicion.get("name") or posicion.get("developer_name") or ""


def _sportmonks_is_starter(lineup: dict) -> bool:
    if lineup.get("formation_field") or lineup.get("formation_position"):
        return True
    tipo = normalizar_nombre(((lineup.get("type") or {}).get("name")) or lineup.get("type_name") or "")
    return tipo in {"starting lineups", "starting lineup", "starting xi", "starter"}


def _sportmonks_obtener_participantes(fixture: dict) -> tuple[dict | None, dict | None]:
    participantes = fixture.get("participants") or []
    if not participantes:
        return None, None

    local = None
    visitante = None
    for participante in participantes:
        meta = participante.get("meta") or participante.get("pivot") or {}
        ubicacion = normalizar_nombre(meta.get("location", ""))
        if ubicacion in {"home", "local"}:
            local = participante
        elif ubicacion in {"away", "visitante"}:
            visitante = participante

    if local and visitante:
        return local, visitante
    if len(participantes) >= 2:
        return participantes[0], participantes[1]
    return participantes[0], None


def _sportmonks_name_score(objetivo: str, candidato: str) -> float:
    if not objetivo or not candidato:
        return 0.0

    objetivo_norm = normalizar_nombre(nombre_visual_equipo(objetivo))
    candidato_norm = normalizar_nombre(nombre_visual_equipo(candidato))
    if not objetivo_norm or not candidato_norm:
        return 0.0
    if objetivo_norm == candidato_norm:
        return 1.0
    if objetivo_norm in candidato_norm or candidato_norm in objetivo_norm:
        return 0.92

    ratio = SequenceMatcher(None, objetivo_norm, candidato_norm).ratio()
    palabras_objetivo = {token for token in objetivo_norm.split() if len(token) >= 3}
    palabras_candidato = {token for token in candidato_norm.split() if len(token) >= 3}
    if palabras_objetivo and palabras_candidato:
        solape = len(palabras_objetivo & palabras_candidato) / max(len(palabras_objetivo), len(palabras_candidato))
        ratio = max(ratio, solape)
    return ratio


def _sportmonks_fixture_score(fixture: dict, nombres_local: list[str], nombres_visitante: list[str]) -> float:
    local_participante, visitante_participante = _sportmonks_obtener_participantes(fixture)
    nombre_local = _sportmonks_participant_name(local_participante or {})
    nombre_visitante = _sportmonks_participant_name(visitante_participante or {})
    score_local = max((_sportmonks_name_score(nombre, nombre_local) for nombre in nombres_local if nombre), default=0.0)
    score_visitante = max(
        (_sportmonks_name_score(nombre, nombre_visitante) for nombre in nombres_visitante if nombre),
        default=0.0,
    )
    return score_local + score_visitante


@st.cache_data(ttl=1200, show_spinner=False)
def buscar_fixture_sportmonks(
    match_date,
    home_team: str,
    away_team: str,
    home_team_raw: str = "",
    away_team_raw: str = "",
    token_hint: str = "",
) -> dict:
    if not _sportmonks_token(token_hint):
        return {"status": "missing_token"}

    fecha = match_date.strftime("%Y-%m-%d")
    fixtures = _sportmonks_paginated(
        f"/fixtures/date/{fecha}",
        params={"include": "participants;league", "per_page": 100},
        max_pages=2,
    )
    if not fixtures:
        return {"status": "no_fixtures"}

    nombres_local = [home_team_raw, home_team, nombre_visual_equipo(home_team)]
    nombres_visitante = [away_team_raw, away_team, nombre_visual_equipo(away_team)]
    candidatos = []
    for fixture in fixtures:
        score = _sportmonks_fixture_score(fixture, nombres_local, nombres_visitante)
        if score < 1.25:
            continue
        candidatos.append((score, fixture))

    if not candidatos:
        return {"status": "fixture_not_found"}

    candidatos.sort(key=lambda item: item[0], reverse=True)
    fixture = candidatos[0][1]
    participante_local, participante_visitante = _sportmonks_obtener_participantes(fixture)
    fecha_fixture = _sportmonks_parse_datetime(fixture.get("starting_at"))
    liga = fixture.get("league") or {}
    return {
        "status": "ok",
        "fixture_id": fixture.get("id"),
        "fixture_name": fixture.get("name") or f"{home_team} vs {away_team}",
        "starting_at": fecha_fixture.isoformat() if fecha_fixture else "",
        "league_name": liga.get("name") or "",
        "home_team": {
            "id": (participante_local or {}).get("id"),
            "name": _sportmonks_participant_name(participante_local or {}),
        },
        "away_team": {
            "id": (participante_visitante or {}).get("id"),
            "name": _sportmonks_participant_name(participante_visitante or {}),
        },
    }


def _sportmonks_detalles_a_mapa(lineup: dict) -> dict[int, float]:
    valores: dict[int, float] = {}
    for detalle in lineup.get("details") or []:
        type_id = detalle.get("type_id") or ((detalle.get("type") or {}).get("id"))
        valor = _sportmonks_parse_float(detalle.get("value"))
        if type_id is None or valor is None:
            continue
        valores[int(type_id)] = valor
    return valores


def _sportmonks_extraer_logs_fixture(fixture: dict, team_id: int | str | None, team_name: str) -> list[dict]:
    if not team_id:
        return []

    fecha_fixture = _sportmonks_parse_datetime(fixture.get("starting_at"))
    participantes = fixture.get("participants") or []
    rival = next((item for item in participantes if str(item.get("id")) != str(team_id)), {})
    rival_nombre = _sportmonks_participant_name(rival)

    logs = []
    for lineup in fixture.get("lineups") or []:
        if str(lineup.get("team_id")) != str(team_id):
            continue
        detalles = _sportmonks_detalles_a_mapa(lineup)
        minutos = detalles.get(SPORTMONKS_PLAYER_STAT_TYPES["minutes_played"], 0.0)
        stats = {
            "shots_on_target": detalles.get(SPORTMONKS_PLAYER_STAT_TYPES["shots_on_target"], 0.0),
            "shots_total": detalles.get(SPORTMONKS_PLAYER_STAT_TYPES["shots_total"], 0.0),
            "fouls_committed": detalles.get(SPORTMONKS_PLAYER_STAT_TYPES["fouls_committed"], 0.0),
            "fouls_drawn": detalles.get(SPORTMONKS_PLAYER_STAT_TYPES["fouls_drawn"], 0.0),
        }
        if minutos <= 0 and not any(stats.values()):
            continue

        jugador = lineup.get("player") or lineup.get("participant") or {}
        logs.append(
            {
                "fixture_id": fixture.get("id"),
                "fixture_name": fixture.get("name") or "",
                "starting_at": fecha_fixture.isoformat() if fecha_fixture else "",
                "team_id": team_id,
                "team_name": team_name,
                "opponent_name": rival_nombre,
                "player_id": jugador.get("id") or lineup.get("player_id"),
                "player_name": _sportmonks_lineup_player_name(lineup),
                "position": _sportmonks_position_name(lineup),
                "is_starter": _sportmonks_is_starter(lineup),
                "minutes": minutos,
                "stats": stats,
            }
        )
    return logs


@st.cache_data(ttl=1200, show_spinner=False)
def obtener_logs_jugadores_sportmonks(
    match_date,
    home_team: str,
    away_team: str,
    home_team_raw: str = "",
    away_team_raw: str = "",
    token_hint: str = "",
) -> dict:
    if not _sportmonks_token(token_hint):
        return {
            "available": False,
            "status": "missing_token",
            "message": "Configura SPORTMONKS_API_TOKEN para activar la capa de jugadores.",
        }

    fixture = buscar_fixture_sportmonks(
        match_date,
        home_team,
        away_team,
        home_team_raw,
        away_team_raw,
        token_hint=token_hint,
    )
    if fixture.get("status") != "ok":
        return {
            "available": False,
            "status": fixture.get("status", "fixture_not_found"),
            "message": "No he podido enlazar este partido con un fixture de Sportmonks.",
            "fixture": fixture,
        }

    fecha_inicio = (match_date - timedelta(days=220)).strftime("%Y-%m-%d")
    fecha_fin = (match_date - timedelta(days=1)).strftime("%Y-%m-%d")
    include = "participants;lineups.details;lineups.player;lineups.detailedposition"
    filtros = "lineupDetailTypes:42,56,86,96,119"

    team_payloads = []
    all_logs: list[dict] = []

    for side in ["home_team", "away_team"]:
        equipo = fixture.get(side) or {}
        team_id = equipo.get("id")
        team_name = equipo.get("name") or (home_team if side == "home_team" else away_team)
        if not team_id:
            team_payloads.append({"team_id": None, "team_name": team_name, "fixtures_sampled": 0, "logs": []})
            continue

        fixtures = _sportmonks_paginated(
            f"/fixtures/between/{fecha_inicio}/{fecha_fin}/{team_id}",
            params={"include": include, "filters": filtros, "per_page": 50},
            max_pages=2,
        )

        fixtures_validos = []
        team_logs: list[dict] = []
        for item in fixtures:
            if str(item.get("id")) == str(fixture.get("fixture_id")):
                continue
            logs_fixture = _sportmonks_extraer_logs_fixture(item, team_id, team_name)
            if not logs_fixture:
                continue
            fixtures_validos.append(item.get("id"))
            team_logs.extend(logs_fixture)
            if len(fixtures_validos) >= 8:
                break

        team_payloads.append(
            {
                "team_id": team_id,
                "team_name": team_name,
                "fixtures_sampled": len(fixtures_validos),
                "logs": team_logs,
            }
        )
        all_logs.extend(team_logs)

    if not all_logs:
        return {
            "available": False,
            "status": "no_logs",
            "message": "Sportmonks no ha devuelto logs de jugador utiles para este cruce.",
            "fixture": fixture,
            "teams": team_payloads,
            "player_logs": [],
        }

    return {
        "available": True,
        "status": "ok",
        "provider": "Sportmonks",
        "fixture": fixture,
        "teams": team_payloads,
        "player_logs": all_logs,
    }
