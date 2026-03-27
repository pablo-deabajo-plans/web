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
    initial_sidebar_state="expanded",
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
                --bg-main: #07101d;
                --bg-panel: linear-gradient(145deg, rgba(7,16,29,0.96), rgba(14,24,42,0.96));
                --bg-card: linear-gradient(180deg, rgba(16,29,54,0.98), rgba(9,16,29,0.98));
                --line: rgba(96, 165, 250, 0.18);
                --text: #e8f1ff;
                --muted: #90a6c8;
                --accent: #00e5a8;
                --accent-2: #3b82f6;
                --warning: #ffd166;
                --danger: #ff6b6b;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(0, 229, 168, 0.14), transparent 28%),
                    radial-gradient(circle at top right, rgba(59, 130, 246, 0.18), transparent 24%),
                    linear-gradient(180deg, #07101d 0%, #0b1425 100%);
                color: var(--text);
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(5, 10, 20, 0.98), rgba(8, 18, 34, 0.98));
                border-right: 1px solid var(--line);
            }

            .block-container {
                padding-top: 1.5rem;
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
                font-size: 2.3rem;
                color: #ffffff;
            }

            .hero p {
                margin: 0.55rem 0 0 0;
                color: var(--muted);
                font-size: 1rem;
            }

            .section-title {
                margin: 1rem 0 0.75rem 0;
                font-size: 1.08rem;
                font-weight: 800;
                letter-spacing: 0.03em;
                color: #ffffff;
                text-transform: uppercase;
            }

            .panel {
                background: var(--bg-card);
                border: 1px solid var(--line);
                border-radius: 20px;
                padding: 1rem;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
                height: 100%;
            }

            .signal-card {
                background: var(--bg-card);
                border: 1px solid var(--line);
                border-radius: 18px;
                padding: 1rem;
                min-height: 158px;
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
                margin-top: 0.75rem;
                padding: 0.28rem 0.6rem;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 800;
                color: #04111d;
                background: var(--warning);
            }

            .mini-stat {
                border-radius: 16px;
                padding: 0.9rem 1rem;
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.06);
                margin-bottom: 0.8rem;
            }

            .mini-stat strong {
                display: block;
                color: #ffffff;
                font-size: 1rem;
            }

            .mini-stat span {
                color: var(--muted);
                font-size: 0.88rem;
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

            .kelly-box {
                border-radius: 20px;
                padding: 1.2rem;
                background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(0,229,168,0.08));
                border: 1px solid rgba(96, 165, 250, 0.22);
                margin-top: 1rem;
            }

            .kelly-main {
                font-size: 1.75rem;
                font-weight: 800;
                color: #ffffff;
            }

            .kelly-sub {
                color: var(--muted);
                margin-top: 0.3rem;
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


def calcular_stats(df: pd.DataFrame, equipo: str) -> dict | None:
    if "HomeTeam" not in df.columns:
        return None

    casa = df[df["HomeTeam"] == equipo]
    fuera = df[df["AwayTeam"] == equipo]
    pj_total = len(casa) + len(fuera)
    if pj_total == 0:
        return None

    todos = df[(df["HomeTeam"] == equipo) | (df["AwayTeam"] == equipo)].copy()
    ultimos_5 = todos.tail(5)
    pj_rec = len(ultimos_5)

    gf_rec = sum(fila["FTHG"] if fila["HomeTeam"] == equipo else fila["FTAG"] for _, fila in ultimos_5.iterrows())
    gc_rec = sum(fila["FTAG"] if fila["HomeTeam"] == equipo else fila["FTHG"] for _, fila in ultimos_5.iterrows())

    gf = casa["FTHG"].sum() + fuera["FTAG"].sum()
    gc = casa["FTAG"].sum() + fuera["FTHG"].sum()

    if "HC" in df.columns and "AC" in df.columns:
        cf = casa["HC"].sum() + fuera["AC"].sum()
        cc = casa["AC"].sum() + fuera["HC"].sum()
    else:
        cf = 4.5 * pj_total
        cc = 4.5 * pj_total

    return {
        "gf": gf / pj_total,
        "gc": gc / pj_total,
        "cf": cf / pj_total,
        "cc": cc / pj_total,
        "gf_rec": gf_rec / pj_rec if pj_rec else gf / pj_total,
        "gc_rec": gc_rec / pj_rec if pj_rec else gc / pj_total,
    }


def simular_partido(xg_local: float, xg_visitante: float, xc_local: float, xc_visitante: float) -> dict:
    goles_local = np.random.poisson(xg_local, SIMULACIONES)
    goles_visitante = np.random.poisson(xg_visitante, SIMULACIONES)
    corners_local = np.random.poisson(xc_local, SIMULACIONES)
    corners_visitante = np.random.poisson(xc_visitante, SIMULACIONES)

    marcadores = [f"{x}-{y}" for x, y in zip(goles_local, goles_visitante)]
    marcador_probable = Counter(marcadores).most_common(1)[0][0]

    return {
        "1": float(np.mean(goles_local > goles_visitante)),
        "X": float(np.mean(goles_local == goles_visitante)),
        "2": float(np.mean(goles_local < goles_visitante)),
        "BTTS": float(np.mean((goles_local > 0) & (goles_visitante > 0))),
        "O25": float(np.mean((goles_local + goles_visitante) > 2.5)),
        "Corn_Home": float(np.mean(corners_local)),
        "Corn_Away": float(np.mean(corners_visitante)),
        "Over9.5_Corn": float(np.mean((corners_local + corners_visitante) > 9.5)),
        "Marcador": marcador_probable,
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
        {"nombre": f"Victoria {local}", "prob": resultado["1"], "tipo": "prob"},
        {"nombre": "Empate", "prob": resultado["X"], "tipo": "prob"},
        {"nombre": f"Victoria {visitante}", "prob": resultado["2"], "tipo": "prob"},
        {"nombre": "Ambos marcan", "prob": resultado["BTTS"], "tipo": "prob"},
        {"nombre": "Over 2.5 goles", "prob": resultado["O25"], "tipo": "prob"},
        {"nombre": "Over 9.5 corners", "prob": resultado["Over9.5_Corn"], "tipo": "prob"},
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


def render_valor_esperado_card(titulo: str, valor: float, subtitulo: str) -> None:
    st.markdown(
        f"""
        <div class="signal-card">
            <div class="signal-label">{titulo}</div>
            <div class="signal-value">{valor:.1f}</div>
            <div class="signal-quote">{subtitulo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_resumen_equipo(nombre: str, stats: dict) -> None:
    st.markdown(
        f"""
        <div class="mini-stat">
            <strong>{nombre}</strong>
            <span>GF {stats['gf']:.2f} | GC {stats['gc']:.2f} | Corners for {stats['cf']:.2f} | Corners against {stats['cc']:.2f}</span>
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


def guardar_analisis(df: pd.DataFrame, liga: str, local: str, visitante: str) -> dict | None:
    stats_local = calcular_stats(df, local)
    stats_visitante = calcular_stats(df, visitante)

    if not stats_local or not stats_visitante:
        return None

    xg_local = (
        (
            (stats_local["gf"] * 0.4 + stats_local["gf_rec"] * 0.6)
            + (stats_visitante["gc"] * 0.4 + stats_visitante["gc_rec"] * 0.6)
        )
        / 2
    ) * 1.12
    xg_visitante = (
        (
            (stats_visitante["gf"] * 0.4 + stats_visitante["gf_rec"] * 0.6)
            + (stats_local["gc"] * 0.4 + stats_local["gc_rec"] * 0.6)
        )
        / 2
    )
    xc_local = ((stats_local["cf"] + stats_visitante["cc"]) / 2) * 1.15
    xc_visitante = (stats_visitante["cf"] + stats_local["cc"]) / 2
    resultado = simular_partido(xg_local, xg_visitante, xc_local, xc_visitante)

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
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


inyectar_estilos()

if "analysis" not in st.session_state:
    st.session_state["analysis"] = None

st.markdown(
    """
    <div class="hero">
        <h1>Gordon BetScanner Pro</h1>
        <p>Motor Poisson para trading de futbol con lectura de value, comparador de cuotas y stake con Kelly.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## Modo Trader")
    liga_seleccionada = st.selectbox("Liga", list(URLS_LIGAS.keys()))
    df = descargar_datos(URLS_LIGAS[liga_seleccionada]) if liga_seleccionada else None

    if df is not None and "HomeTeam" in df.columns:
        equipos = sorted(df["HomeTeam"].dropna().unique())
    else:
        equipos = []

    local = st.selectbox("Equipo local", equipos) if equipos else None
    visitante_index = 1 if len(equipos) > 1 else 0
    visitante = st.selectbox("Equipo visitante", equipos, index=visitante_index) if equipos else None
    analizar = st.button("Escanear partido", use_container_width=True)

    st.caption("La simulacion mezcla historico reciente, forma y ventaja local.")

    if analizar:
        if local == visitante:
            st.session_state["analysis"] = None
            st.error("No puedes enfrentar al mismo equipo contra si mismo.")
        elif df is None:
            st.session_state["analysis"] = None
            st.error("No se pudieron descargar los datos de la liga.")
        else:
            with st.spinner("Ejecutando motor Poisson y calibrando mercados..."):
                analisis = guardar_analisis(df, liga_seleccionada, local, visitante)
            st.session_state["analysis"] = analisis
            if analisis is None:
                st.error("No hay datos suficientes para uno de los equipos seleccionados.")


analisis = st.session_state.get("analysis")

if df is None:
    st.error("No se pudieron descargar los datos de la liga seleccionada.")
elif not equipos:
    st.warning("No hay equipos disponibles en la liga cargada.")
elif analisis is None:
    st.info("Configura el partido en la barra lateral y pulsa Escanear partido para lanzar el analisis.")
else:
    resultado = analisis["resultado"]
    stats_local = analisis["stats_local"]
    stats_visitante = analisis["stats_visitante"]
    mercados = construir_mercados(resultado, analisis["local"], analisis["visitante"])

    st.success(f"Analisis completado: {analisis['local']} vs {analisis['visitante']}")

    top_left, top_right = st.columns([1.5, 1])

    with top_left:
        st.markdown('<div class="section-title">Mercado 1X2</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            render_signal_card(f"Victoria {analisis['local']}", resultado["1"])
        with c2:
            render_signal_card("Empate", resultado["X"])
        with c3:
            render_signal_card(f"Victoria {analisis['visitante']}", resultado["2"])

        st.markdown('<div class="section-title">Mercado de Goles</div>', unsafe_allow_html=True)
        c4, c5 = st.columns(2)
        with c4:
            render_signal_card("Ambos marcan", resultado["BTTS"])
        with c5:
            render_signal_card("Over 2.5 goles", resultado["O25"])

        st.markdown('<div class="section-title">Mercado de Corners</div>', unsafe_allow_html=True)
        c6, c7, c8 = st.columns(3)
        with c6:
            render_valor_esperado_card(f"Corners {analisis['local']}", resultado["Corn_Home"], "Esperados")
        with c7:
            render_signal_card("Over 9.5 corners", resultado["Over9.5_Corn"])
        with c8:
            render_valor_esperado_card(f"Corners {analisis['visitante']}", resultado["Corn_Away"], "Esperados")

    with top_right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### Radar del Partido")
        st.metric("Marcador mas probable", resultado["Marcador"])
        st.metric("xG local estimado", f"{analisis['xg_local']:.2f}")
        st.metric("xG visitante estimado", f"{analisis['xg_visitante']:.2f}")
        render_resumen_equipo(analisis["local"], stats_local)
        render_resumen_equipo(analisis["visitante"], stats_visitante)
        st.caption(
            "Las tarjetas en verde marcan mercados con probabilidad matematica superior al 65%."
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">Comparador Cuota Real vs Cuota Justa</div>', unsafe_allow_html=True)
    st.caption("Introduce las cuotas reales de tu casa y el panel colorea al instante si hay ventaja matematica.")

    inputs_cols = st.columns(3)
    cuotas_usuario: dict[str, float] = {}
    for indice, mercado in enumerate(mercados):
        clave = safe_key(mercado["nombre"])
        cuota_default = max(1.05, round(cuota_justa(mercado["prob"]), 2))
        with inputs_cols[indice % 3]:
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
            f"Mejor oportunidad actual: {mejor_oportunidad['market']} con edge {mejor_oportunidad['edge'] * 100:.2f}%."
        )
    else:
        st.warning("Con las cuotas actuales no aparece una ventaja positiva clara frente a la cuota justa.")

    st.markdown('<div class="section-title">Calculadora de Stake con Kelly</div>', unsafe_allow_html=True)
    nombres_mercado = [mercado["nombre"] for mercado in mercados]
    mercado_kelly = st.selectbox("Mercado para stake", nombres_mercado)
    mercado_seleccionado = next(item for item in mercados if item["nombre"] == mercado_kelly)
    cuota_seleccionada = cuotas_usuario[mercado_kelly]

    c_kelly_1, c_kelly_2 = st.columns(2)
    with c_kelly_1:
        bankroll = st.number_input("Bankroll disponible", min_value=1.0, value=100.0, step=10.0)
    with c_kelly_2:
        modo_kelly = st.selectbox("Intensidad Kelly", ["Full Kelly", "Half Kelly", "Quarter Kelly"], index=1)

    factor_kelly = {"Full Kelly": 1.0, "Half Kelly": 0.5, "Quarter Kelly": 0.25}[modo_kelly]
    porcentaje_kelly_bruto = stake_kelly(mercado_seleccionado["prob"], cuota_seleccionada)
    porcentaje_kelly = porcentaje_kelly_bruto * factor_kelly
    stake_recomendado = bankroll * porcentaje_kelly
    edge_kelly = (mercado_seleccionado["prob"] * cuota_seleccionada) - 1

    st.markdown(
        f"""
        <div class="kelly-box">
            <div class="signal-label">Mercado seleccionado</div>
            <div class="kelly-main">{mercado_kelly}</div>
            <div class="kelly-sub">Prob IA {mercado_seleccionado['prob'] * 100:.2f}% | Cuota justa @{cuota_justa(mercado_seleccionado['prob']):.2f} | Cuota casa @{cuota_seleccionada:.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    k1, k2, k3 = st.columns(3)
    k1.metric("% bankroll a invertir", f"{porcentaje_kelly * 100:.2f}%")
    k2.metric("Stake recomendado", f"{stake_recomendado:.2f} u")
    k3.metric("Edge esperado", f"{edge_kelly * 100:.2f}%")

    if porcentaje_kelly > 0:
        st.success("La cuota supera la cuota justa. Kelly recomienda exposicion positiva en este mercado.")
    else:
        st.warning("La cuota no supera la cuota justa. Kelly recomienda stake 0.")

    st.caption(
        "Formula Kelly: f = ((cuota - 1) * p - (1 - p)) / (cuota - 1). Half Kelly y Quarter Kelly reducen volatilidad."
    )

    st.markdown('<div class="section-title">Picks Favoritos</div>', unsafe_allow_html=True)
    botones_favoritos = st.columns([1, 1.2, 2])
    with botones_favoritos[0]:
        guardar_pick = st.button("Guardar pick favorito", use_container_width=True)
    with botones_favoritos[1]:
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
                "offered_odds": round(cuota_seleccionada, 4),
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
