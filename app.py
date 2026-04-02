from __future__ import annotations

import io
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Gordon BetScanner Pro",
    layout="wide",
)


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

VALUE_BET_THRESHOLD = 0.65
SIMULACIONES = 50000
FAVORITES_FILE = Path("data/favorite_picks.json")
LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")
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


def inyectar_estilos() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg-panel: linear-gradient(145deg, rgba(7,16,29,0.96), rgba(14,24,42,0.96));
                --bg-card: linear-gradient(180deg, rgba(16,29,54,0.98), rgba(9,16,29,0.98));
                --line: rgba(96, 165, 250, 0.18);
                --text: #e8f1ff;
                --muted: #90a6c8;
                --warning: #ffd166;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(0, 229, 168, 0.14), transparent 28%),
                    radial-gradient(circle at top right, rgba(59, 130, 246, 0.18), transparent 24%),
                    linear-gradient(180deg, #07101d 0%, #0b1425 100%);
                color: var(--text);
            }

            .block-container {
                padding-top: 1.4rem;
                padding-bottom: 2rem;
            }

            .hero {
                background: var(--bg-panel);
                border: 1px solid var(--line);
                border-radius: 24px;
                padding: 1.6rem;
                box-shadow: 0 20px 70px rgba(0, 0, 0, 0.28);
                margin-bottom: 1rem;
            }

            .hero h1 {
                margin: 0;
                font-size: 2.35rem;
                color: #ffffff;
            }

            .hero p {
                margin: 0.55rem 0 0 0;
                color: var(--muted);
                font-size: 1rem;
            }

            .search-shell {
                background: rgba(7, 16, 29, 0.74);
                border: 1px solid rgba(96, 165, 250, 0.16);
                border-radius: 22px;
                padding: 1rem 1rem 0.25rem 1rem;
                margin-bottom: 1rem;
                backdrop-filter: blur(14px);
            }

            .search-shell h3 {
                color: #ffffff;
                margin: 0 0 0.2rem 0;
                font-size: 1.02rem;
            }

            .search-shell p {
                color: var(--muted);
                margin: 0 0 0.75rem 0;
                font-size: 0.9rem;
            }

            .section-title {
                margin: 0.9rem 0 0.75rem 0;
                font-size: 1.06rem;
                font-weight: 800;
                letter-spacing: 0.04em;
                color: #ffffff;
                text-transform: uppercase;
            }

            .panel {
                background: var(--bg-card);
                border: 1px solid var(--line);
                border-radius: 20px;
                padding: 1rem;
                height: 100%;
            }

            .signal-card {
                background: var(--bg-card);
                border: 1px solid var(--line);
                border-radius: 18px;
                padding: 1rem;
                min-height: 155px;
            }

            .signal-card.value-bet {
                border: 1px solid rgba(0, 229, 168, 0.62);
                box-shadow: 0 0 0 1px rgba(0,229,168,0.18), 0 0 24px rgba(0,229,168,0.16);
                background: linear-gradient(180deg, rgba(0,229,168,0.14), rgba(9,16,29,0.98));
            }

            .signal-label {
                color: var(--muted);
                font-size: 0.84rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .signal-value {
                font-size: 2rem;
                font-weight: 800;
                color: #ffffff;
                margin-top: 0.25rem;
            }

            .signal-quote {
                color: #9bd7ff;
                font-size: 0.95rem;
                margin-top: 0.35rem;
            }

            .signal-tag {
                display: inline-block;
                margin-top: 0.7rem;
                padding: 0.28rem 0.6rem;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 800;
                color: #04111d;
                background: var(--warning);
            }

            .summary-band {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.8rem;
                margin: 0.6rem 0 1rem 0;
            }

            .summary-chip {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 16px;
                padding: 0.9rem 1rem;
            }

            .summary-chip strong {
                color: #ffffff;
                display: block;
                font-size: 1.1rem;
            }

            .summary-chip span {
                color: var(--muted);
                font-size: 0.86rem;
            }

            .split-card {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 18px;
                padding: 1rem;
                margin-bottom: 0.9rem;
            }

            .split-card h4 {
                color: #ffffff;
                margin: 0 0 0.65rem 0;
            }

            .split-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.55rem;
            }

            .mini-stat {
                border-radius: 14px;
                padding: 0.75rem 0.85rem;
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.05);
            }

            .mini-stat strong {
                display: block;
                color: #ffffff;
                font-size: 0.96rem;
            }

            .mini-stat span {
                color: var(--muted);
                font-size: 0.82rem;
            }

            .odds-row {
                display: grid;
                grid-template-columns: 1.6fr 0.8fr 0.8fr 0.8fr 0.8fr;
                gap: 0.75rem;
                align-items: center;
                padding: 0.9rem 1rem;
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.07);
                margin-bottom: 0.65rem;
                background: rgba(255,255,255,0.03);
            }

            .odds-row.value {
                border-color: rgba(0,229,168,0.45);
                background: linear-gradient(90deg, rgba(0,229,168,0.12), rgba(255,255,255,0.03));
            }

            .odds-row.flat {
                border-color: rgba(59,130,246,0.45);
                background: linear-gradient(90deg, rgba(59,130,246,0.12), rgba(255,255,255,0.03));
            }

            .odds-row.bad {
                border-color: rgba(255,107,107,0.35);
                background: linear-gradient(90deg, rgba(255,107,107,0.10), rgba(255,255,255,0.03));
            }

            .odds-head {
                display: grid;
                grid-template-columns: 1.6fr 0.8fr 0.8fr 0.8fr 0.8fr;
                gap: 0.75rem;
                padding: 0 1rem 0.45rem 1rem;
                color: var(--muted);
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }

            .favorite-card {
                background: var(--bg-card);
                border: 1px solid var(--line);
                border-radius: 18px;
                padding: 1rem;
                margin-bottom: 0.8rem;
            }

            .favorite-card strong {
                color: #ffffff;
                font-size: 1rem;
            }

            .favorite-card p {
                color: var(--muted);
                margin: 0.35rem 0 0 0;
                font-size: 0.9rem;
            }

            .fixture-card {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 20px;
                padding: 1rem;
                margin-bottom: 0.85rem;
                min-height: 170px;
                box-shadow: 0 16px 40px rgba(0, 0, 0, 0.14);
            }

            .fixture-card.active {
                border-color: rgba(0,229,168,0.45);
                background: linear-gradient(180deg, rgba(0,229,168,0.10), rgba(9,16,29,0.98));
                box-shadow: 0 0 0 1px rgba(0,229,168,0.12), 0 22px 44px rgba(0, 0, 0, 0.2);
            }

            .fixture-meta {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 0.6rem;
                color: var(--muted);
                font-size: 0.82rem;
                margin-bottom: 0.7rem;
            }

            .fixture-teams {
                color: #ffffff;
                font-size: 1.06rem;
                font-weight: 800;
                line-height: 1.35;
                margin-bottom: 0.6rem;
            }

            .fixture-sub {
                color: var(--muted);
                font-size: 0.88rem;
                line-height: 1.45;
            }

            .source-pill {
                display: inline-block;
                padding: 0.24rem 0.58rem;
                border-radius: 999px;
                background: rgba(59,130,246,0.16);
                border: 1px solid rgba(59,130,246,0.24);
                color: #cfe3ff;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                text-transform: uppercase;
            }

            .detail-card {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 18px;
                padding: 1rem;
                margin-bottom: 0.85rem;
                min-height: 145px;
            }

            .detail-card h4 {
                margin: 0 0 0.6rem 0;
                color: #ffffff;
            }

            .detail-card p,
            .detail-card li {
                color: var(--muted);
                font-size: 0.9rem;
                margin: 0.3rem 0;
            }

            .detail-note {
                border-radius: 16px;
                padding: 0.9rem 1rem;
                background: rgba(255, 209, 102, 0.10);
                border: 1px solid rgba(255, 209, 102, 0.22);
                color: #fff4c2;
                margin-bottom: 0.8rem;
            }

            .score-pill {
                display: inline-block;
                margin: 0 0.5rem 0.5rem 0;
                padding: 0.5rem 0.8rem;
                border-radius: 999px;
                background: rgba(59,130,246,0.14);
                border: 1px solid rgba(59,130,246,0.28);
                color: #e7f0ff;
                font-size: 0.86rem;
                font-weight: 700;
            }

            .insight-box {
                border-radius: 18px;
                padding: 1rem;
                background: linear-gradient(135deg, rgba(59,130,246,0.13), rgba(0,229,168,0.08));
                border: 1px solid rgba(96, 165, 250, 0.2);
            }

            .kelly-box {
                border-radius: 20px;
                padding: 1.2rem;
                background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(0,229,168,0.08));
                border: 1px solid rgba(96, 165, 250, 0.22);
                margin-top: 1rem;
            }

            .kelly-main {
                font-size: 1.7rem;
                font-weight: 800;
                color: #ffffff;
            }

            .kelly-sub {
                color: var(--muted);
                margin-top: 0.3rem;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.4rem;
            }

            .stTabs [data-baseweb="tab"] {
                background: rgba(255,255,255,0.04);
                border-radius: 14px;
                padding: 0.55rem 0.9rem;
                color: var(--muted);
            }

            .stTabs [aria-selected="true"] {
                background: linear-gradient(90deg, rgba(0,229,168,0.18), rgba(59,130,246,0.18));
                color: #ffffff;
            }

            div[data-testid="stMetric"] {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 16px;
                padding: 0.8rem;
            }

            .stButton > button {
                border-radius: 14px;
                border: none;
                background: linear-gradient(90deg, #00e5a8, #3b82f6);
                color: #03111d;
                font-weight: 800;
                min-height: 3rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def normalizar_nombre(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    for token in [".", ",", "-", "'", '"']:
        texto = texto.replace(token, " ")
    texto = " ".join(texto.split())
    return texto


def resolver_nombre_equipo(nombre: str, equipos_csv: list[str]) -> str:
    nombre_norm = normalizar_nombre(nombre)
    aliases = {
        "real sociedad ii": "Sociedad B",
        "real sociedad b": "Sociedad B",
        "sociedad b": "Sociedad B",
        "leganes": "Leganes",
        "real zaragoza": "Zaragoza",
        "sporting gijon": "Sp Gijon",
        "deportivo la coruna": "La Coruna",
        "deportivo coruna": "La Coruna",
        "malaga": "Malaga",
        "cadiz": "Cadiz",
        "cordoba": "Cordoba",
        "almeria": "Almeria",
        "mirandes": "Mirandes",
        "castellon": "Castellon",
    }
    if nombre_norm in aliases:
        return aliases[nombre_norm]

    mapa_csv = {normalizar_nombre(equipo): equipo for equipo in equipos_csv}
    if nombre_norm in mapa_csv:
        return mapa_csv[nombre_norm]

    for clave_norm, equipo_real in mapa_csv.items():
        if nombre_norm in clave_norm or clave_norm in nombre_norm:
            return equipo_real
    return nombre


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
    combinado = (
        combinado.sort_values(["priority", "Time", "FixtureLabel"])
        .drop_duplicates(subset=["dedupe_key"], keep="first")
        .drop(columns=["dedupe_key", "priority"])
    )
    return combinado


def extraer_historico(df: pd.DataFrame) -> pd.DataFrame:
    historico = df.copy()
    if "FTHG" in historico.columns and "FTAG" in historico.columns:
        historico = historico[historico["FTHG"].notna() & historico["FTAG"].notna()].copy()
    return historico


def calcular_segmento(df: pd.DataFrame, equipo: str, scope: str) -> dict:
    if scope == "home":
        partidos = df[df["HomeTeam"] == equipo].copy()
        goles_favor = partidos["FTHG"]
        goles_contra = partidos["FTAG"]
        corners_favor = partidos["HC"] if "HC" in partidos.columns else pd.Series([4.5] * len(partidos))
        corners_contra = partidos["AC"] if "AC" in partidos.columns else pd.Series([4.5] * len(partidos))
        victorias = partidos["FTHG"] > partidos["FTAG"]
        empates = partidos["FTHG"] == partidos["FTAG"]
        derrotas = partidos["FTHG"] < partidos["FTAG"]
    elif scope == "away":
        partidos = df[df["AwayTeam"] == equipo].copy()
        goles_favor = partidos["FTAG"]
        goles_contra = partidos["FTHG"]
        corners_favor = partidos["AC"] if "AC" in partidos.columns else pd.Series([4.5] * len(partidos))
        corners_contra = partidos["HC"] if "HC" in partidos.columns else pd.Series([4.5] * len(partidos))
        victorias = partidos["FTAG"] > partidos["FTHG"]
        empates = partidos["FTAG"] == partidos["FTHG"]
        derrotas = partidos["FTAG"] < partidos["FTHG"]
    else:
        casa = df[df["HomeTeam"] == equipo].copy()
        fuera = df[df["AwayTeam"] == equipo].copy()
        partidos = pd.concat([casa, fuera], ignore_index=True)

        if partidos.empty:
            goles_favor = pd.Series(dtype=float)
            goles_contra = pd.Series(dtype=float)
            corners_favor = pd.Series(dtype=float)
            corners_contra = pd.Series(dtype=float)
            victorias = pd.Series(dtype=bool)
            empates = pd.Series(dtype=bool)
            derrotas = pd.Series(dtype=bool)
        else:
            goles_favor = pd.Series(
                [fila["FTHG"] if fila["HomeTeam"] == equipo else fila["FTAG"] for _, fila in partidos.iterrows()]
            )
            goles_contra = pd.Series(
                [fila["FTAG"] if fila["HomeTeam"] == equipo else fila["FTHG"] for _, fila in partidos.iterrows()]
            )
            if "HC" in partidos.columns and "AC" in partidos.columns:
                corners_favor = pd.Series(
                    [fila["HC"] if fila["HomeTeam"] == equipo else fila["AC"] for _, fila in partidos.iterrows()]
                )
                corners_contra = pd.Series(
                    [fila["AC"] if fila["HomeTeam"] == equipo else fila["HC"] for _, fila in partidos.iterrows()]
                )
            else:
                corners_favor = pd.Series([4.5] * len(partidos))
                corners_contra = pd.Series([4.5] * len(partidos))
            victorias = goles_favor > goles_contra
            empates = goles_favor == goles_contra
            derrotas = goles_favor < goles_contra

    pj = int(len(partidos))
    if pj == 0:
        return {
            "pj": 0,
            "gf": 0.0,
            "gc": 0.0,
            "corners_for": 0.0,
            "corners_against": 0.0,
            "win_pct": 0.0,
            "draw_pct": 0.0,
            "loss_pct": 0.0,
            "btts_pct": 0.0,
            "over25_pct": 0.0,
            "clean_sheet_pct": 0.0,
            "fail_score_pct": 0.0,
            "total_goals": 0.0,
        }

    total_goals = goles_favor + goles_contra
    return {
        "pj": pj,
        "gf": float(goles_favor.mean()),
        "gc": float(goles_contra.mean()),
        "corners_for": float(corners_favor.mean()),
        "corners_against": float(corners_contra.mean()),
        "win_pct": float(victorias.mean()),
        "draw_pct": float(empates.mean()),
        "loss_pct": float(derrotas.mean()),
        "btts_pct": float(((goles_favor > 0) & (goles_contra > 0)).mean()),
        "over25_pct": float((total_goals > 2.5).mean()),
        "clean_sheet_pct": float((goles_contra == 0).mean()),
        "fail_score_pct": float((goles_favor == 0).mean()),
        "total_goals": float(total_goals.mean()),
    }


def calcular_stats(df: pd.DataFrame, equipo: str) -> dict:
    todos = calcular_segmento(df, equipo, "all")
    casa = calcular_segmento(df, equipo, "home")
    fuera = calcular_segmento(df, equipo, "away")

    recientes = df[(df["HomeTeam"] == equipo) | (df["AwayTeam"] == equipo)].copy().tail(5)
    pj_rec = len(recientes)
    if pj_rec > 0:
        gf_rec = sum(
            fila["FTHG"] if fila["HomeTeam"] == equipo else fila["FTAG"]
            for _, fila in recientes.iterrows()
        ) / pj_rec
        gc_rec = sum(
            fila["FTAG"] if fila["HomeTeam"] == equipo else fila["FTHG"]
            for _, fila in recientes.iterrows()
        ) / pj_rec
    else:
        gf_rec = todos["gf"]
        gc_rec = todos["gc"]

    return {
        "overall": todos,
        "home": casa,
        "away": fuera,
        "gf_rec": gf_rec,
        "gc_rec": gc_rec,
        "form": calcular_forma(df, equipo, 5),
    }


def calcular_forma(df: pd.DataFrame, equipo: str, n_partidos: int = 5) -> dict:
    partidos = df[(df["HomeTeam"] == equipo) | (df["AwayTeam"] == equipo)].copy().tail(n_partidos)
    if partidos.empty:
        return {
            "matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "points": 0,
            "ppg": 0.0,
            "goal_diff": 0,
            "results": [],
            "streak": "Sin datos",
        }

    resultados = []
    wins = draws = losses = 0
    goal_diff = 0
    for _, fila in partidos.iterrows():
        gf = fila["FTHG"] if fila["HomeTeam"] == equipo else fila["FTAG"]
        gc = fila["FTAG"] if fila["HomeTeam"] == equipo else fila["FTHG"]
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
    streak = "-".join(resultados)
    return {
        "matches": len(partidos),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": puntos,
        "ppg": puntos / len(partidos),
        "goal_diff": goal_diff,
        "results": resultados,
        "streak": streak,
    }


def calcular_h2h(df: pd.DataFrame, local: str, visitante: str, limite: int = 6) -> dict:
    cruces = df[
        ((df["HomeTeam"] == local) & (df["AwayTeam"] == visitante))
        | ((df["HomeTeam"] == visitante) & (df["AwayTeam"] == local))
    ].copy()
    cruces = cruces.tail(limite)

    if cruces.empty:
        return {
            "matches": 0,
            "local_wins": 0,
            "away_wins": 0,
            "draws": 0,
            "local_win_pct": 0.0,
            "away_win_pct": 0.0,
            "avg_total_goals": 0.0,
            "btts_pct": 0.0,
            "over25_pct": 0.0,
            "recent_labels": [],
        }

    local_wins = away_wins = draws = 0
    etiquetas = []
    total_goals = []
    btts = []
    over25 = []

    for _, fila in cruces.iterrows():
        goles_local = fila["FTHG"] if fila["HomeTeam"] == local else fila["FTAG"]
        goles_visitante = fila["FTAG"] if fila["HomeTeam"] == local else fila["FTHG"]
        total = goles_local + goles_visitante
        total_goals.append(total)
        btts.append(goles_local > 0 and goles_visitante > 0)
        over25.append(total > 2.5)
        etiquetas.append(f"{local} {int(goles_local)}-{int(goles_visitante)} {visitante}")

        if goles_local > goles_visitante:
            local_wins += 1
        elif goles_local < goles_visitante:
            away_wins += 1
        else:
            draws += 1

    partidos = len(cruces)
    return {
        "matches": partidos,
        "local_wins": local_wins,
        "away_wins": away_wins,
        "draws": draws,
        "local_win_pct": local_wins / partidos,
        "away_win_pct": away_wins / partidos,
        "avg_total_goals": float(np.mean(total_goals)),
        "btts_pct": float(np.mean(btts)),
        "over25_pct": float(np.mean(over25)),
        "recent_labels": etiquetas[::-1],
    }


def simular_partido(xg_local: float, xg_visitante: float, xc_local: float, xc_visitante: float) -> dict:
    goles_local = np.random.poisson(xg_local, SIMULACIONES)
    goles_visitante = np.random.poisson(xg_visitante, SIMULACIONES)
    corners_local = np.random.poisson(xc_local, SIMULACIONES)
    corners_visitante = np.random.poisson(xc_visitante, SIMULACIONES)

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


def safe_key(texto: str) -> str:
    return (
        texto.lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("+", "plus")
        .replace("/", "_")
        .replace("-", "_")
    )


def asegurar_favoritos() -> None:
    FAVORITES_FILE.parent.mkdir(parents=True, exist_ok=True)


def cargar_favoritos() -> list[dict]:
    asegurar_favoritos()
    if not FAVORITES_FILE.exists():
        return []
    try:
        with FAVORITES_FILE.open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, list) else []
    except Exception:
        return []


def guardar_favoritos(favoritos: list[dict]) -> None:
    asegurar_favoritos()
    with FAVORITES_FILE.open("w", encoding="utf-8") as archivo:
        json.dump(favoritos, archivo, indent=2, ensure_ascii=True)


def agregar_favorito(entrada: dict) -> None:
    favoritos = cargar_favoritos()
    favoritos.insert(0, entrada)
    guardar_favoritos(favoritos[:30])


def eliminar_favorito(favorite_id: str) -> None:
    favoritos = [item for item in cargar_favoritos() if item.get("id") != favorite_id]
    guardar_favoritos(favoritos)


def vaciar_favoritos() -> None:
    guardar_favoritos([])


def construir_mercados(resultado: dict, local: str, visitante: str) -> list[dict]:
    return [
        {"nombre": f"Victoria {local}", "prob": resultado["1"]},
        {"nombre": "Empate", "prob": resultado["X"]},
        {"nombre": f"Victoria {visitante}", "prob": resultado["2"]},
        {"nombre": "Ambos marcan", "prob": resultado["BTTS"]},
        {"nombre": "Over 2.5 goles", "prob": resultado["O25"]},
        {"nombre": "Over 9.5 corners", "prob": resultado["Over9.5_Corn"]},
    ]


def render_signal_card(titulo: str, probabilidad: float) -> None:
    es_value = probabilidad >= VALUE_BET_THRESHOLD
    clase = "signal-card value-bet" if es_value else "signal-card"
    tag = '<div class="signal-tag">VALUE BET</div>' if es_value else ""
    st.markdown(
        f"""
        <div class="{clase}">
            <div class="signal-label">{titulo}</div>
            <div class="signal-value">{probabilidad * 100:.1f}%</div>
            <div class="signal-quote">Cuota justa @{cuota_justa(probabilidad):.2f}</div>
            {tag}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_expected_card(titulo: str, valor: float, subtitulo: str) -> None:
    st.markdown(
        f"""
        <div class="signal-card">
            <div class="signal-label">{titulo}</div>
            <div class="signal-value">{valor:.2f}</div>
            <div class="signal-quote">{subtitulo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_band(analisis: dict) -> None:
    resultado = analisis["resultado"]
    fecha_partido = analisis["match_date"].strftime("%d/%m/%Y") if analisis.get("match_date") else analisis["timestamp"]
    st.markdown(
        f"""
        <div class="summary-band">
            <div class="summary-chip">
                <strong>{analisis['local']} vs {analisis['visitante']}</strong>
                <span>{analisis['liga']} | {fecha_partido}</span>
            </div>
            <div class="summary-chip">
                <strong>{resultado['Marcador']}</strong>
                <span>Marcador mas probable</span>
            </div>
            <div class="summary-chip">
                <strong>{resultado['Total_Goals']:.2f}</strong>
                <span>Goles totales esperados</span>
            </div>
            <div class="summary-chip">
                <strong>{resultado['Total_Corners']:.2f}</strong>
                <span>Corners totales esperados</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_split_panel(titulo: str, stats: dict) -> None:
    st.markdown(
        f"""
        <div class="split-card">
            <h4>{titulo}</h4>
            <div class="split-grid">
                <div class="mini-stat"><strong>{stats['pj']}</strong><span>Partidos</span></div>
                <div class="mini-stat"><strong>{stats['gf']:.2f}</strong><span>Goles a favor</span></div>
                <div class="mini-stat"><strong>{stats['gc']:.2f}</strong><span>Goles en contra</span></div>
                <div class="mini-stat"><strong>{stats['corners_for']:.2f}</strong><span>Corners for</span></div>
                <div class="mini-stat"><strong>{stats['corners_against']:.2f}</strong><span>Corners against</span></div>
                <div class="mini-stat"><strong>{stats['win_pct'] * 100:.1f}%</strong><span>Victorias</span></div>
                <div class="mini-stat"><strong>{stats['draw_pct'] * 100:.1f}%</strong><span>Empates</span></div>
                <div class="mini-stat"><strong>{stats['loss_pct'] * 100:.1f}%</strong><span>Derrotas</span></div>
                <div class="mini-stat"><strong>{stats['btts_pct'] * 100:.1f}%</strong><span>BTTS</span></div>
                <div class="mini-stat"><strong>{stats['over25_pct'] * 100:.1f}%</strong><span>Over 2.5</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_comparador_cuotas(filas: list[dict]) -> None:
    st.markdown(
        """
        <div class="odds-head">
            <div>Mercado</div>
            <div>Prob IA</div>
            <div>Justa</div>
            <div>Casa</div>
            <div>Edge</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for fila in filas:
        if fila["edge"] > 0:
            clase = "value"
        elif fila["offered_odds"] >= fila["fair_odds"]:
            clase = "flat"
        else:
            clase = "bad"

        st.markdown(
            f"""
            <div class="odds-row {clase}">
                <div><strong>{fila['market']}</strong></div>
                <div>{fila['prob'] * 100:.1f}%</div>
                <div>@{fila['fair_odds']:.2f}</div>
                <div>@{fila['offered_odds']:.2f}</div>
                <div>{fila['edge'] * 100:.2f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_fixture_cards(partidos: pd.DataFrame, fecha_objetivo, hoy) -> pd.Series | None:
    if partidos.empty:
        return None

    titulo_lista = (
        "Tarjetas de partidos de hoy"
        if fecha_objetivo == hoy
        else f"Tarjetas de partidos del {fecha_objetivo.strftime('%d/%m/%Y')}"
    )
    st.markdown(f'<div class="section-title">{titulo_lista}</div>', unsafe_allow_html=True)

    opciones_partidos = partidos["FixtureLabel"].tolist()
    if st.session_state.get("fixture_label") not in opciones_partidos:
        st.session_state["fixture_label"] = opciones_partidos[0]

    filas_partidos = partidos.to_dict("records")
    for inicio in range(0, len(filas_partidos), 3):
        bloque = filas_partidos[inicio : inicio + 3]
        cols = st.columns(3)
        for col, partido in zip(cols, bloque):
            seleccion_actual = st.session_state.get("fixture_label") == partido["FixtureLabel"]
            clase = "fixture-card active" if seleccion_actual else "fixture-card"
            with col:
                st.markdown(
                    f"""
                    <div class="{clase}">
                        <div class="fixture-meta">
                            <span>{partido.get('MatchDate').strftime('%d/%m/%Y') if partido.get('MatchDate') else 'Sin fecha'} {partido.get('Time', '').strip()}</span>
                            <span class="source-pill">{partido.get('Source', 'CSV')}</span>
                        </div>
                        <div class="fixture-teams">{partido.get('HomeTeamRaw', partido.get('HomeTeam', 'TBD'))}<br>vs<br>{partido.get('AwayTeamRaw', partido.get('AwayTeam', 'TBD'))}</div>
                        <div class="fixture-sub">Abre este panel para ver lectura del modelo, comparativa, mercado y detalles en vivo.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                boton = "Panel cargado" if seleccion_actual else "Ver estadisticas"
                if st.button(
                    boton,
                    key=f"fixture_{safe_key(partido['FixtureLabel'])}_{inicio}",
                    use_container_width=True,
                    disabled=seleccion_actual,
                ):
                    st.session_state["fixture_label"] = partido["FixtureLabel"]
                    st.rerun()
    seleccion_fixture = st.session_state.get("fixture_label")
    return partidos[partidos["FixtureLabel"] == seleccion_fixture].iloc[0]


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
                "team": team.get("displayName") or team.get("shortDisplayName") or "Equipo",
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
            f"{(local.get('team') or {}).get('displayName', 'Local')} {local.get('score', '-')} - {visitante.get('score', '-')} {(visitante.get('team') or {}).get('displayName', 'Visitante')}"
        )
    return etiquetas


def extraer_disponibilidad_espn(resumen: dict) -> dict:
    texto = json.dumps(resumen, ensure_ascii=True).lower()
    tiene_lineups = any(token in texto for token in ["lineup", "formation", "startingxi", "starter", "substitutes"])
    tiene_bajas = any(token in texto for token in ["injur", "susp"])
    tiene_xg = any(token in texto for token in ["expectedgoals", "\"xg\"", "shotmap"])

    return {
        "lineups": tiene_lineups,
        "injuries": tiene_bajas,
        "xg_shots": tiene_xg,
    }


def render_contexto_feed_espn(resumen: dict, analisis: dict) -> None:
    if not resumen:
        st.markdown(
            """
            <div class="detail-note">
                No hay feed enriquecido disponible para este partido. El panel sigue funcionando con el modelo historico y las cuotas manuales.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    contexto_mercado = extraer_contexto_mercado_espn(resumen)
    forma_espn = extraer_detalles_forma_espn(resumen)
    h2h_espn = extraer_head_to_head_espn(resumen)
    disponibilidad = extraer_disponibilidad_espn(resumen)

    if not all(disponibilidad.values()):
        avisos = []
        if not disponibilidad["lineups"]:
            avisos.append("alineaciones")
        if not disponibilidad["injuries"]:
            avisos.append("lesiones/sanciones")
        if not disponibilidad["xg_shots"]:
            avisos.append("xG por disparo")
        aviso_texto = ", ".join(avisos)
        st.markdown(
            f"""
            <div class="detail-note">
                La fuente abierta del partido no expone ahora mismo {aviso_texto}. Cuando el feed no lo trae, la app lo marca como no disponible en lugar de inventarlo.
            </div>
            """,
            unsafe_allow_html=True,
        )

    top_left, top_mid, top_right = st.columns(3)
    with top_left:
        lineas_mercado = []
        if contexto_mercado["available"]:
            lineas_mercado.append(f"<p>Proveedor: {contexto_mercado['provider']}</p>")
            lineas_mercado.append(f"<p>Mercado: {contexto_mercado['details']}</p>")
            if contexto_mercado["home_ml"] is not None:
                texto = (
                    f"1 local: ML {contexto_mercado['home_ml']} | Decimal @{contexto_mercado['home_decimal']:.2f}"
                    if contexto_mercado["home_decimal"] is not None
                    else f"1 local: ML {contexto_mercado['home_ml']}"
                )
                lineas_mercado.append(f"<p>{texto}</p>")
            if contexto_mercado["draw_ml"] is not None:
                texto = (
                    f"X empate: ML {contexto_mercado['draw_ml']} | Decimal @{contexto_mercado['draw_decimal']:.2f}"
                    if contexto_mercado["draw_decimal"] is not None
                    else f"X empate: ML {contexto_mercado['draw_ml']}"
                )
                lineas_mercado.append(f"<p>{texto}</p>")
            if contexto_mercado["away_ml"] is not None:
                texto = (
                    f"2 visitante: ML {contexto_mercado['away_ml']} | Decimal @{contexto_mercado['away_decimal']:.2f}"
                    if contexto_mercado["away_decimal"] is not None
                    else f"2 visitante: ML {contexto_mercado['away_ml']}"
                )
                lineas_mercado.append(f"<p>{texto}</p>")
            if contexto_mercado["over_under"] is not None:
                lineas_mercado.append(f"<p>Linea total: {contexto_mercado['over_under']:.2f}</p>")
            if contexto_mercado["spread"] is not None:
                lineas_mercado.append(f"<p>Spread: {contexto_mercado['spread']:.2f}</p>")
        else:
            lineas_mercado.append("<p>Sin cuotas abiertas en este feed.</p>")
        st.markdown(
            f'<div class="detail-card"><h4>Mercado en tiempo real</h4>{"".join(lineas_mercado)}</div>',
            unsafe_allow_html=True,
        )

    with top_mid:
        lineas_bajas = []
        if disponibilidad["lineups"]:
            lineas_bajas.append("<p>El feed indica que hay estructura de alineacion disponible, pero no estandarizada en todas las ligas.</p>")
        else:
            lineas_bajas.append("<p>Alineaciones confirmadas/probables no disponibles en la fuente abierta consultada para este partido.</p>")
        if disponibilidad["injuries"]:
            lineas_bajas.append("<p>Se detectaron campos de disponibilidad del jugador en el feed.</p>")
        else:
            lineas_bajas.append("<p>Lesiones y sanciones no publicadas por esta fuente abierta para este cruce.</p>")
        st.markdown(
            f'<div class="detail-card"><h4>Alineaciones y bajas</h4>{"".join(lineas_bajas)}</div>',
            unsafe_allow_html=True,
        )

    with top_right:
        lineas_xg = []
        if disponibilidad["xg_shots"]:
            lineas_xg.append("<p>El feed trae referencias a xG o shot map para este partido.</p>")
        else:
            lineas_xg.append("<p>No hay xG shot-by-shot en abierto para este evento.</p>")
        lineas_xg.append(
            f"<p>xG estimado del modelo: {analisis['local']} {analisis['xg_local']:.2f} | {analisis['visitante']} {analisis['xg_visitante']:.2f}</p>"
        )
        lineas_xg.append("<p>El motor prepartido sigue apoyandose en temporada, casa/fuera, forma y H2H.</p>")
        st.markdown(
            f'<div class="detail-card"><h4>xG por disparo</h4>{"".join(lineas_xg)}</div>',
            unsafe_allow_html=True,
        )

    bottom_left, bottom_right = st.columns(2)
    with bottom_left:
        lineas_forma = []
        if forma_espn:
            for entrada in forma_espn:
                lineas_forma.append(f"<p>{entrada['team']}: {entrada['summary']}</p>")
        else:
            lineas_forma.append("<p>Sin resumen de forma extra en la fuente abierta.</p>")
        st.markdown(
            f'<div class="detail-card"><h4>Lectura de forma del feed</h4>{"".join(lineas_forma)}</div>',
            unsafe_allow_html=True,
        )

    with bottom_right:
        lineas_h2h = []
        if h2h_espn:
            for item in h2h_espn:
                lineas_h2h.append(f"<p>{item}</p>")
        else:
            lineas_h2h.append("<p>Sin head to head adicional en el feed abierto.</p>")
        if contexto_mercado["pickcenter"]:
            lineas_h2h.append("<p>Consenso del mercado:</p>")
            for pick in contexto_mercado["pickcenter"]:
                detalle = pick.get("details") or pick.get("summary") or "Sin detalle"
                lineas_h2h.append(f"<p>- {detalle}</p>")
        st.markdown(
            f'<div class="detail-card"><h4>Head to head del feed</h4>{"".join(lineas_h2h)}</div>',
            unsafe_allow_html=True,
        )


def tabla_comparativa(
    local: str,
    visitante: str,
    local_home: dict,
    visitante_away: dict,
    local_all: dict,
    visitante_all: dict,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Metric": "GF escenario",
                f"{local} casa": round(local_home["gf"], 2),
                f"{visitante} fuera": round(visitante_away["gf"], 2),
                "Diff local-away": round(local_home["gf"] - visitante_away["gf"], 2),
            },
            {
                "Metric": "GC escenario",
                f"{local} casa": round(local_home["gc"], 2),
                f"{visitante} fuera": round(visitante_away["gc"], 2),
                "Diff local-away": round(local_home["gc"] - visitante_away["gc"], 2),
            },
            {
                "Metric": "Corners for escenario",
                f"{local} casa": round(local_home["corners_for"], 2),
                f"{visitante} fuera": round(visitante_away["corners_for"], 2),
                "Diff local-away": round(local_home["corners_for"] - visitante_away["corners_for"], 2),
            },
            {
                "Metric": "BTTS escenario",
                f"{local} casa": round(local_home["btts_pct"] * 100, 1),
                f"{visitante} fuera": round(visitante_away["btts_pct"] * 100, 1),
                "Diff local-away": round((local_home["btts_pct"] - visitante_away["btts_pct"]) * 100, 1),
            },
            {
                "Metric": "Over 2.5 escenario",
                f"{local} casa": round(local_home["over25_pct"] * 100, 1),
                f"{visitante} fuera": round(visitante_away["over25_pct"] * 100, 1),
                "Diff local-away": round((local_home["over25_pct"] - visitante_away["over25_pct"]) * 100, 1),
            },
        ]
    )


def construir_insights(analisis: dict) -> list[str]:
    resultado = analisis["resultado"]
    local_home = analisis["stats_local"]["home"]
    visitante_away = analisis["stats_visitante"]["away"]
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

    return insights[:4]


def guardar_analisis(df: pd.DataFrame, liga: str, local: str, visitante: str, match_date=None, match_label: str = "") -> dict | None:
    historico = extraer_historico(df)
    stats_local = calcular_stats(historico, local)
    stats_visitante = calcular_stats(historico, visitante)
    h2h = calcular_h2h(historico, local, visitante, 6)

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
    ajuste_h2h = 0.0
    if h2h["matches"] > 0:
        ajuste_h2h = max(-0.05, min(0.05, (h2h["local_win_pct"] - h2h["away_win_pct"]) * 0.03))

    xg_local = ((ataque_local + defensa_visitante) / 2) * 1.10 * (1 + ajuste_forma + ajuste_h2h)
    xg_visitante = ((ataque_visitante + defensa_local) / 2) * (1 - ajuste_forma - (ajuste_h2h / 2))
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

    resultado = simular_partido(xg_local, xg_visitante, xc_local, xc_visitante)
    mercados = construir_mercados(resultado, local, visitante)

    return {
        "liga": liga,
        "local": local,
        "visitante": visitante,
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
        "mercados": mercados,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


inyectar_estilos()

if "analysis" not in st.session_state:
    st.session_state["analysis"] = None
if "analysis_signature" not in st.session_state:
    st.session_state["analysis_signature"] = None
if "solo_hoy_toggle" not in st.session_state:
    st.session_state["solo_hoy_toggle"] = True
if "last_league" not in st.session_state:
    st.session_state["last_league"] = None

st.markdown(
    """
    <div class="hero">
        <h1>Gordon BetScanner Pro</h1>
        <p>Buscador superior, analisis en una sola pantalla y pestanas operativas para scouting, comparativa y trading.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="search-shell">
        <h3>Buscador de partido</h3>
        <p>Selecciona la liga, filtra por fecha o por hoy y pincha un partido de la lista para abrir su panel de estadisticas en la misma pantalla.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

top_1, top_2, top_3, top_4 = st.columns([1.15, 1.0, 1.25, 0.7])

with top_1:
    liga_seleccionada = st.selectbox("Liga", list(URLS_LIGAS.keys()))

if st.session_state.get("last_league") != liga_seleccionada:
    st.session_state["solo_hoy_toggle"] = True
    st.session_state["fixture_label"] = None
    st.session_state["last_league"] = liga_seleccionada

df = descargar_datos(URLS_LIGAS[liga_seleccionada]) if liga_seleccionada else None
calendario_csv = preparar_calendario(df) if df is not None else pd.DataFrame()
equipos_csv = sorted(df["HomeTeam"].dropna().unique()) if df is not None and "HomeTeam" in df.columns else []
league_id = ESPN_LEAGUE_IDS.get(liga_seleccionada, "")

fechas_disponibles = sorted([fecha for fecha in calendario_csv.get("MatchDate", pd.Series(dtype=object)).dropna().unique()])
hoy = datetime.now(LOCAL_TIMEZONE).date()
partidos_hoy_espn = descargar_fixture_espn(league_id, hoy) if league_id else pd.DataFrame()
hay_partidos_hoy = hoy in fechas_disponibles or not partidos_hoy_espn.empty
fechas_futuras = [fecha for fecha in fechas_disponibles if fecha >= hoy]
fecha_default = hoy if hay_partidos_hoy else (fechas_futuras[0] if fechas_futuras else (fechas_disponibles[-1] if fechas_disponibles else hoy))

with top_2:
    solo_hoy = st.toggle("Partidos de hoy", key="solo_hoy_toggle")

with top_3:
    fecha_partido = st.date_input("Fecha", value=fecha_default, disabled=solo_hoy)

fecha_objetivo = hoy if solo_hoy else fecha_partido
partidos_csv = calendario_csv[calendario_csv["MatchDate"] == fecha_objetivo].copy() if not calendario_csv.empty else pd.DataFrame()
usar_fallback_espn = fecha_objetivo >= hoy or partidos_csv.empty
partidos_espn = partidos_hoy_espn if fecha_objetivo == hoy else (descargar_fixture_espn(league_id, fecha_objetivo) if usar_fallback_espn and league_id else pd.DataFrame())
partidos_filtrados = fusionar_calendarios(partidos_csv, partidos_espn, equipos_csv)
if partidos_filtrados.empty and not calendario_csv.empty and not solo_hoy:
    partidos_filtrados = fusionar_calendarios(calendario_csv, pd.DataFrame(), equipos_csv)

with top_4:
    st.metric("Partidos", len(partidos_filtrados))

if solo_hoy and partidos_filtrados.empty:
    st.warning("No aparecen partidos para hoy ni en el CSV ni en la fuente de respaldo. Puedes desactivar el filtro y elegir otra fecha.")
elif partidos_filtrados.empty and not calendario_csv.empty:
    st.warning("No hay partidos para esa fecha. Te muestro el selector completo de la liga como respaldo.")

if not partidos_filtrados.empty:
    partido_seleccionado = render_fixture_cards(partidos_filtrados, fecha_objetivo, hoy)
else:
    partido_seleccionado = None

local = partido_seleccionado["HomeTeam"] if partido_seleccionado is not None else None
visitante = partido_seleccionado["AwayTeam"] if partido_seleccionado is not None else None

if df is None:
    st.session_state["analysis"] = None
    st.session_state["analysis_signature"] = None
elif partido_seleccionado is None:
    st.session_state["analysis"] = None
    st.session_state["analysis_signature"] = None
else:
    firma_actual = (
        liga_seleccionada,
        partido_seleccionado["MatchDate"],
        local,
        visitante,
        partido_seleccionado.get("Source", ""),
    )
    if st.session_state.get("analysis_signature") != firma_actual:
        with st.spinner("Ejecutando motor Poisson y construyendo panel de trading..."):
            st.session_state["analysis"] = guardar_analisis(
                df,
                liga_seleccionada,
                local,
                visitante,
                match_date=partido_seleccionado["MatchDate"],
                match_label=partido_seleccionado["FixtureLabel"],
            )
        st.session_state["analysis_signature"] = firma_actual
        if st.session_state["analysis"] is None:
            st.error("No hay datos suficientes para construir el analisis de este cruce.")

analisis = st.session_state.get("analysis")
resumen_espn = {}
if partido_seleccionado is not None and league_id:
    event_id = str(partido_seleccionado.get("EventId", "") or "")
    if event_id:
        resumen_espn = descargar_resumen_espn(league_id, event_id)

if df is None:
    st.error("No se pudieron descargar los datos de la liga seleccionada.")
elif calendario_csv.empty and partidos_espn.empty:
    st.warning("No hay partidos disponibles en el calendario cargado.")
elif analisis is None:
    st.info("Usa el buscador superior y selecciona un partido de la lista para cargar el analisis en esta misma pantalla.")
else:
    resultado = analisis["resultado"]
    mercados = analisis["mercados"]
    render_summary_band(analisis)

    overview_left, overview_right = st.columns([1.45, 1])
    with overview_left:
        st.markdown('<div class="section-title">Senales rapidas</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            render_signal_card(f"Victoria {analisis['local']}", resultado["1"])
        with c2:
            render_signal_card("Empate", resultado["X"])
        with c3:
            render_signal_card(f"Victoria {analisis['visitante']}", resultado["2"])

    with overview_right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### Radar instantaneo")
        st.metric("Marcador mas probable", resultado["Marcador"])
        st.metric("xG local", f"{analisis['xg_local']:.2f}")
        st.metric("xG visitante", f"{analisis['xg_visitante']:.2f}")
        st.metric("Corners esperados", f"{resultado['Total_Corners']:.2f}")
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Como calcula las probabilidades el modelo"):
        st.write(
            "El modelo combina estadisticas de temporada, rendimiento en casa/fuera, forma reciente y un ajuste suave por enfrentamientos directos recientes antes de simular el partido con Poisson."
        )
        st.write(
            f"- {analisis['local']}: usa medias globales, medias como local y forma de los ultimos 5 partidos ({analisis['stats_local']['form']['streak']})."
        )
        st.write(
            f"- {analisis['visitante']}: usa medias globales, medias como visitante y forma de los ultimos 5 partidos ({analisis['stats_visitante']['form']['streak']})."
        )
        st.write(
            f"- H2H directo: {analisis['h2h']['matches']} cruces recientes entre ambos, con media de {analisis['h2h']['avg_total_goals']:.2f} goles."
        )
        st.write(
            "- Con esas medias se estiman goles esperados y corners esperados, y luego se lanzan 50.000 simulaciones Poisson para obtener 1X2, BTTS, Over 2.5, corners y marcador mas probable."
        )

    tab_stats, tab_compare, tab_match, tab_feed, tab_odds = st.tabs(
        [
            "Estadisticas generales",
            "Comparativa equipos",
            "Posibles estadisticas del partido",
            "Feed del partido",
            "Comparador cuota real vs cuota justa",
        ]
    )

    with tab_stats:
        st.markdown('<div class="section-title">Radiografia de cada equipo</div>', unsafe_allow_html=True)
        eq_1, eq_2 = st.columns(2)

        with eq_1:
            st.markdown(f"### {analisis['local']}")
            render_split_panel("Global", analisis["stats_local"]["overall"])
            render_split_panel("En casa", analisis["stats_local"]["home"])
            render_split_panel("Fuera", analisis["stats_local"]["away"])

        with eq_2:
            st.markdown(f"### {analisis['visitante']}")
            render_split_panel("Global", analisis["stats_visitante"]["overall"])
            render_split_panel("En casa", analisis["stats_visitante"]["home"])
            render_split_panel("Fuera", analisis["stats_visitante"]["away"])

    with tab_compare:
        st.markdown('<div class="section-title">Local en casa vs visitante fuera</div>', unsafe_allow_html=True)
        comparativa_df = tabla_comparativa(
            analisis["local"],
            analisis["visitante"],
            analisis["stats_local"]["home"],
            analisis["stats_visitante"]["away"],
            analisis["stats_local"]["overall"],
            analisis["stats_visitante"]["overall"],
        )
        st.dataframe(comparativa_df, use_container_width=True, hide_index=True)

        insight_left, insight_right = st.columns([1.3, 1])
        with insight_left:
            st.markdown('<div class="insight-box">', unsafe_allow_html=True)
            st.markdown("### Lectura tactica del cruce")
            for insight in construir_insights(analisis):
                st.write(f"- {insight}")
            st.markdown("</div>", unsafe_allow_html=True)
        with insight_right:
            st.metric("GF local en casa", f"{analisis['stats_local']['home']['gf']:.2f}")
            st.metric("GC visitante fuera", f"{analisis['stats_visitante']['away']['gc']:.2f}")
            st.metric("Corners local en casa", f"{analisis['stats_local']['home']['corners_for']:.2f}")
            st.metric("Corners visitante fuera", f"{analisis['stats_visitante']['away']['corners_for']:.2f}")

        st.markdown("### Forma reciente y enfrentamientos directos")
        form_left, form_right, h2h_col = st.columns(3)
        with form_left:
            st.metric(f"PPG ultimos 5 {analisis['local']}", f"{analisis['stats_local']['form']['ppg']:.2f}")
            st.metric(f"Racha {analisis['local']}", analisis["stats_local"]["form"]["streak"])
        with form_right:
            st.metric(f"PPG ultimos 5 {analisis['visitante']}", f"{analisis['stats_visitante']['form']['ppg']:.2f}")
            st.metric(f"Racha {analisis['visitante']}", analisis["stats_visitante"]["form"]["streak"])
        with h2h_col:
            st.metric("H2H local", f"{analisis['h2h']['local_wins']}")
            st.metric("H2H visitante", f"{analisis['h2h']['away_wins']}")
            st.metric("Empates H2H", f"{analisis['h2h']['draws']}")

        if analisis["h2h"]["matches"] > 0:
            st.caption("Ultimos cruces directos detectados")
            for etiqueta in analisis["h2h"]["recent_labels"]:
                st.write(f"- {etiqueta}")
        else:
            st.caption("No se detectaron cruces directos recientes entre ambos en la base historica cargada.")

    with tab_match:
        st.markdown('<div class="section-title">Posibles estadisticas del partido</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_signal_card("Ambos marcan", resultado["BTTS"])
        with m2:
            render_signal_card("Over 2.5 goles", resultado["O25"])
        with m3:
            render_signal_card("Over 9.5 corners", resultado["Over9.5_Corn"])
        with m4:
            render_expected_card("Total goals", resultado["Total_Goals"], "Media simulada")

        s1, s2, s3, s4 = st.columns(4)
        s1.metric(f"{analisis['local']} +1.5 goles", f"{resultado['Home_Over15'] * 100:.1f}%")
        s2.metric(f"{analisis['visitante']} +1.5 goles", f"{resultado['Away_Over15'] * 100:.1f}%")
        s3.metric(f"{analisis['local']} puerta a cero", f"{resultado['Home_CleanSheet'] * 100:.1f}%")
        s4.metric(f"{analisis['visitante']} puerta a cero", f"{resultado['Away_CleanSheet'] * 100:.1f}%")

        c_a, c_b, c_c = st.columns(3)
        c_a.metric(f"Corners {analisis['local']}", f"{resultado['Corn_Home']:.2f}")
        c_b.metric("Corners totales", f"{resultado['Total_Corners']:.2f}")
        c_c.metric(f"Corners {analisis['visitante']}", f"{resultado['Corn_Away']:.2f}")

        st.markdown("### Marcadores mas probables")
        marcador_html = "".join(
            f"<span class='score-pill'>{marcador} - {prob * 100:.2f}%</span>"
            for marcador, prob in [(item[0], item[1] / SIMULACIONES) for item in resultado["TopScores"]]
        )
        st.markdown(marcador_html, unsafe_allow_html=True)

    with tab_feed:
        st.markdown('<div class="section-title">Feed abierto del partido</div>', unsafe_allow_html=True)
        st.caption(
            "Aqui ves lo que la fuente abierta del partido expone de verdad: mercado en tiempo real, forma extra y referencias live. Si no hay alineaciones, lesiones o xG por disparo, la app lo marca como no disponible."
        )
        render_contexto_feed_espn(resumen_espn, analisis)

    with tab_odds:
        st.markdown('<div class="section-title">Comparador de cuotas, Kelly y favoritos</div>', unsafe_allow_html=True)
        st.caption("Introduce las cuotas reales y el panel colorea si la casa te esta regalando valor o te esta cobrando caro.")

        odds_cols = st.columns(3)
        cuotas_usuario: dict[str, float] = {}
        for indice, mercado in enumerate(mercados):
            clave = safe_key(mercado["nombre"])
            cuota_default = max(1.05, round(cuota_justa(mercado["prob"]), 2))
            with odds_cols[indice % 3]:
                cuotas_usuario[mercado["nombre"]] = st.number_input(
                    f"Cuota {mercado['nombre']}",
                    min_value=1.01,
                    value=cuota_default,
                    step=0.01,
                    key=f"odd_{clave}",
                )

        filas_comparador = []
        for mercado in mercados:
            cuota_real = cuotas_usuario[mercado["nombre"]]
            cuota_fair = cuota_justa(mercado["prob"])
            edge = (mercado["prob"] * cuota_real) - 1
            filas_comparador.append(
                {
                    "market": mercado["nombre"],
                    "prob": mercado["prob"],
                    "fair_odds": cuota_fair,
                    "offered_odds": cuota_real,
                    "edge": edge,
                }
            )

        render_comparador_cuotas(filas_comparador)

        mejor_oportunidad = max(filas_comparador, key=lambda fila: fila["edge"])
        if mejor_oportunidad["edge"] > 0:
            st.success(
                f"Mejor value actual: {mejor_oportunidad['market']} con edge {mejor_oportunidad['edge'] * 100:.2f}%."
            )
        else:
            st.warning("No hay ventaja positiva clara con las cuotas cargadas ahora mismo.")

        st.markdown("### Stake con Kelly")
        nombres_mercado = [mercado["nombre"] for mercado in mercados]
        mercado_kelly = st.selectbox("Mercado para stake", nombres_mercado)
        mercado_seleccionado = next(item for item in mercados if item["nombre"] == mercado_kelly)
        cuota_seleccionada = cuotas_usuario[mercado_kelly]

        k_left, k_mid, k_right = st.columns(3)
        with k_left:
            bankroll = st.number_input("Bankroll disponible", min_value=1.0, value=100.0, step=10.0)
        with k_mid:
            modo_kelly = st.selectbox("Intensidad Kelly", ["Full Kelly", "Half Kelly", "Quarter Kelly"], index=1)
        with k_right:
            cuota_input = st.number_input(
                "Cuota usada en Kelly",
                min_value=1.01,
                value=float(cuota_seleccionada),
                step=0.01,
                key=f"kelly_custom_odd_{safe_key(mercado_kelly)}",
            )

        factor_kelly = {"Full Kelly": 1.0, "Half Kelly": 0.5, "Quarter Kelly": 0.25}[modo_kelly]
        porcentaje_kelly_bruto = stake_kelly(mercado_seleccionado["prob"], cuota_input)
        porcentaje_kelly = porcentaje_kelly_bruto * factor_kelly
        stake_recomendado = bankroll * porcentaje_kelly
        edge_kelly = (mercado_seleccionado["prob"] * cuota_input) - 1

        st.markdown(
            f"""
            <div class="kelly-box">
                <div class="signal-label">Mercado seleccionado</div>
                <div class="kelly-main">{mercado_kelly}</div>
                <div class="kelly-sub">Prob IA {mercado_seleccionado['prob'] * 100:.2f}% | Cuota justa @{cuota_justa(mercado_seleccionado['prob']):.2f} | Cuota casa @{cuota_input:.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        r1, r2, r3 = st.columns(3)
        r1.metric("% bankroll a invertir", f"{porcentaje_kelly * 100:.2f}%")
        r2.metric("Stake recomendado", f"{stake_recomendado:.2f} u")
        r3.metric("Edge esperado", f"{edge_kelly * 100:.2f}%")

        if porcentaje_kelly > 0:
            st.success("La cuota supera la cuota justa. Kelly recomienda exposicion positiva.")
        else:
            st.warning("La cuota no supera la cuota justa. Kelly recomienda stake 0.")

        st.caption(
            "Formula Kelly: f = ((cuota - 1) * p - (1 - p)) / (cuota - 1). Half Kelly y Quarter Kelly reducen volatilidad."
        )

        st.markdown("### Picks favoritos")
        acciones_fav = st.columns([1, 1.2, 2])
        with acciones_fav[0]:
            guardar_pick = st.button("Guardar pick favorito", use_container_width=True)
        with acciones_fav[1]:
            limpiar_picks = st.button("Vaciar favoritos", use_container_width=True)

        if guardar_pick:
            agregar_favorito(
                {
                    "id": str(uuid4()),
                    "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "liga": analisis["liga"],
                    "match": f"{analisis['local']} vs {analisis['visitante']}",
                    "market": mercado_kelly,
                    "prob": round(mercado_seleccionado["prob"], 6),
                    "fair_odds": round(cuota_justa(mercado_seleccionado["prob"]), 4),
                    "offered_odds": round(cuota_input, 4),
                    "edge": round(edge_kelly, 6),
                    "kelly_pct": round(porcentaje_kelly, 6),
                    "stake_units": round(stake_recomendado, 2),
                }
            )
            st.success("Pick guardado en favoritos.")
            st.rerun()

        if limpiar_picks:
            vaciar_favoritos()
            st.warning("Favoritos eliminados.")
            st.rerun()

        favoritos = cargar_favoritos()
        if not favoritos:
            st.info("Todavia no has guardado picks favoritos.")
        else:
            for favorito in favoritos:
                cols = st.columns([5, 1])
                with cols[0]:
                    st.markdown(
                        f"""
                        <div class="favorite-card">
                            <strong>{favorito['market']}</strong>
                            <p>{favorito['match']} | {favorito['liga']}</p>
                            <p>Prob IA {favorito['prob'] * 100:.2f}% | Justa @{favorito['fair_odds']:.2f} | Casa @{favorito['offered_odds']:.2f}</p>
                            <p>Edge {favorito['edge'] * 100:.2f}% | Kelly {favorito['kelly_pct'] * 100:.2f}% | Stake {favorito['stake_units']:.2f} u | {favorito['saved_at']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with cols[1]:
                    if st.button("Eliminar", key=f"delete_{favorito['id']}", use_container_width=True):
                        eliminar_favorito(favorito["id"])
                        st.rerun()
