from __future__ import annotations

import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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
    "Serie A": "https://www.football-data.co.uk/mmz4281/2526/I1.csv",
    "Bundesliga": "https://www.football-data.co.uk/mmz4281/2526/D1.csv",
    "Ligue 1": "https://www.football-data.co.uk/mmz4281/2526/F1.csv",
    "Eredivisie": "https://www.football-data.co.uk/mmz4281/2526/N1.csv",
    "Portugal": "https://www.football-data.co.uk/mmz4281/2526/P1.csv",
}

VALUE_BET_THRESHOLD = 0.65
SIMULACIONES = 50000
FAVORITES_FILE = Path("data/favorite_picks.json")


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
    st.markdown(
        f"""
        <div class="summary-band">
            <div class="summary-chip">
                <strong>{analisis['local']} vs {analisis['visitante']}</strong>
                <span>{analisis['liga']} | {analisis['timestamp']}</span>
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


def guardar_analisis(df: pd.DataFrame, liga: str, local: str, visitante: str) -> dict | None:
    stats_local = calcular_stats(df, local)
    stats_visitante = calcular_stats(df, visitante)

    if stats_local["overall"]["pj"] == 0 or stats_visitante["overall"]["pj"] == 0:
        return None

    xg_local = (
        (
            (stats_local["overall"]["gf"] * 0.4 + stats_local["gf_rec"] * 0.6)
            + (stats_visitante["overall"]["gc"] * 0.4 + stats_visitante["gc_rec"] * 0.6)
        )
        / 2
    ) * 1.12
    xg_visitante = (
        (
            (stats_visitante["overall"]["gf"] * 0.4 + stats_visitante["gf_rec"] * 0.6)
            + (stats_local["overall"]["gc"] * 0.4 + stats_local["gc_rec"] * 0.6)
        )
        / 2
    )
    xc_local = ((stats_local["home"]["corners_for"] + stats_visitante["away"]["corners_against"]) / 2) * 1.15
    xc_visitante = (stats_visitante["away"]["corners_for"] + stats_local["home"]["corners_against"]) / 2

    resultado = simular_partido(xg_local, xg_visitante, xc_local, xc_visitante)
    mercados = construir_mercados(resultado, local, visitante)

    return {
        "liga": liga,
        "local": local,
        "visitante": visitante,
        "resultado": resultado,
        "stats_local": stats_local,
        "stats_visitante": stats_visitante,
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
        <p>Selecciona la liga, filtra equipos arriba del todo y analiza el partido sin salir de la misma pantalla.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

top_1, top_2, top_3, top_4, top_5 = st.columns([1.2, 1.1, 1.2, 1.2, 0.9])

with top_1:
    liga_seleccionada = st.selectbox("Liga", list(URLS_LIGAS.keys()))

df = descargar_datos(URLS_LIGAS[liga_seleccionada]) if liga_seleccionada else None
if df is not None and "HomeTeam" in df.columns:
    equipos = sorted(df["HomeTeam"].dropna().unique())
else:
    equipos = []

with top_2:
    filtro_equipos = st.text_input("Buscar equipo", placeholder="Ej: Real, City, Milan")

equipos_filtrados = [equipo for equipo in equipos if filtro_equipos.lower() in equipo.lower()] if filtro_equipos else equipos
if not equipos_filtrados:
    equipos_filtrados = equipos

with top_3:
    local = st.selectbox("Equipo local", equipos_filtrados) if equipos_filtrados else None

opciones_visitante = [equipo for equipo in equipos_filtrados if equipo != local] if local else equipos_filtrados
if not opciones_visitante:
    opciones_visitante = [equipo for equipo in equipos if equipo != local]

with top_4:
    visitante = st.selectbox("Equipo visitante", opciones_visitante) if opciones_visitante else None

with top_5:
    analizar = st.button("Analizar", use_container_width=True)

if analizar:
    if df is None:
        st.session_state["analysis"] = None
        st.error("No se pudieron descargar los datos de la liga.")
    elif not local or not visitante:
        st.session_state["analysis"] = None
        st.error("Selecciona dos equipos validos.")
    elif local == visitante:
        st.session_state["analysis"] = None
        st.error("No puedes analizar al mismo equipo contra si mismo.")
    else:
        with st.spinner("Ejecutando motor Poisson y construyendo panel de trading..."):
            st.session_state["analysis"] = guardar_analisis(df, liga_seleccionada, local, visitante)
        if st.session_state["analysis"] is None:
            st.error("No hay datos suficientes para construir el analisis de este cruce.")

analisis = st.session_state.get("analysis")

if df is None:
    st.error("No se pudieron descargar los datos de la liga seleccionada.")
elif not equipos:
    st.warning("No hay equipos disponibles en la liga cargada.")
elif analisis is None:
    st.info("Usa el buscador superior y pulsa Analizar para cargar el partido en esta misma pantalla.")
else:
    seleccion_actual = (liga_seleccionada, local, visitante)
    seleccion_analizada = (analisis["liga"], analisis["local"], analisis["visitante"])
    if seleccion_actual != seleccion_analizada:
        st.warning("Has cambiado la seleccion superior. Pulsa Analizar para refrescar el tablero del partido.")

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

    tab_stats, tab_compare, tab_match, tab_odds = st.tabs(
        [
            "Estadisticas generales",
            "Comparativa equipos",
            "Posibles estadisticas del partido",
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
