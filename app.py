import io
from collections import Counter

import numpy as np
import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Gordon BetScanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


URLS_LIGAS = {
    "Premier League 🏴": "https://www.football-data.co.uk/mmz4281/2526/E0.csv",
    "LaLiga 🇪🇸": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "Serie A 🇮🇹": "https://www.football-data.co.uk/mmz4281/2526/I1.csv",
    "Bundesliga 🇩🇪": "https://www.football-data.co.uk/mmz4281/2526/D1.csv",
    "Ligue 1 🇫🇷": "https://www.football-data.co.uk/mmz4281/2526/F1.csv",
    "Holanda 🇳🇱": "https://www.football-data.co.uk/mmz4281/2526/N1.csv",
    "Portugal 🇵🇹": "https://www.football-data.co.uk/mmz4281/2526/P1.csv",
}

VALUE_BET_THRESHOLD = 0.65
SIMULACIONES = 50000


def inyectar_estilos() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg-main: #08111f;
                --bg-panel: linear-gradient(145deg, rgba(8,17,31,0.92), rgba(15,26,46,0.9));
                --bg-card: linear-gradient(180deg, rgba(17,29,52,0.95), rgba(10,17,32,0.95));
                --line: rgba(96, 165, 250, 0.18);
                --text: #e5eefc;
                --muted: #8ca3c7;
                --accent: #00e5a8;
                --accent-soft: rgba(0, 229, 168, 0.12);
                --alert: #ffd166;
                --danger: #ff6b6b;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(0, 229, 168, 0.12), transparent 28%),
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
                border-radius: 22px;
                padding: 1.5rem;
                box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
                margin-bottom: 1rem;
            }

            .hero h1 {
                margin: 0;
                font-size: 2.2rem;
                color: white;
            }

            .hero p {
                margin: 0.5rem 0 0 0;
                color: var(--muted);
                font-size: 1rem;
            }

            .section-title {
                margin: 1rem 0 0.75rem 0;
                font-size: 1.1rem;
                font-weight: 700;
                letter-spacing: 0.02em;
                color: white;
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
                min-height: 160px;
            }

            .signal-card.value-bet {
                border: 1px solid rgba(0, 229, 168, 0.65);
                box-shadow: 0 0 0 1px rgba(0,229,168,0.18), 0 0 24px rgba(0,229,168,0.16);
                background:
                    linear-gradient(180deg, rgba(0,229,168,0.14), rgba(10,17,32,0.96));
            }

            .signal-label {
                color: var(--muted);
                font-size: 0.88rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .signal-value {
                font-size: 2rem;
                font-weight: 800;
                color: white;
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
                font-size: 0.8rem;
                font-weight: 700;
                color: #04111d;
                background: var(--alert);
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
                color: white;
                font-size: 1.05rem;
            }

            .mini-stat span {
                color: var(--muted);
                font-size: 0.88rem;
            }

            .kelly-box {
                border-radius: 20px;
                padding: 1.2rem;
                background:
                    linear-gradient(135deg, rgba(59,130,246,0.15), rgba(0,229,168,0.08));
                border: 1px solid rgba(96, 165, 250, 0.22);
                margin-top: 1rem;
            }

            .kelly-main {
                font-size: 2rem;
                font-weight: 800;
                color: white;
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
        req = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        req.raise_for_status()
        df = pd.read_csv(io.StringIO(req.content.decode("utf-8", errors="ignore")))
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

    gf_rec = sum(r["FTHG"] if r["HomeTeam"] == equipo else r["FTAG"] for _, r in ultimos_5.iterrows())
    gc_rec = sum(r["FTAG"] if r["HomeTeam"] == equipo else r["FTHG"] for _, r in ultimos_5.iterrows())

    gf = casa["FTHG"].sum() + fuera["FTAG"].sum()
    gc = casa["FTAG"].sum() + fuera["FTHG"].sum()

    cf = casa["HC"].sum() + fuera["AC"].sum() if "HC" in df.columns and "AC" in df.columns else 4.5 * pj_total
    cc = casa["AC"].sum() + fuera["HC"].sum() if "HC" in df.columns and "AC" in df.columns else 4.5 * pj_total

    return {
        "gf": gf / pj_total,
        "gc": gc / pj_total,
        "cf": cf / pj_total,
        "cc": cc / pj_total,
        "gf_rec": gf_rec / pj_rec if pj_rec > 0 else gf / pj_total,
        "gc_rec": gc_rec / pj_rec if pj_rec > 0 else gc / pj_total,
    }


def simular_partido(xg_l: float, xg_v: float, xc_l: float, xc_v: float) -> dict:
    h = np.random.poisson(xg_l, SIMULACIONES)
    a = np.random.poisson(xg_v, SIMULACIONES)
    hc = np.random.poisson(xc_l, SIMULACIONES)
    ac = np.random.poisson(xc_v, SIMULACIONES)

    resultados = [f"{x}-{y}" for x, y in zip(h, a)]
    marcador_probable = Counter(resultados).most_common(1)[0][0]

    return {
        "1": np.mean(h > a),
        "X": np.mean(h == a),
        "2": np.mean(h < a),
        "BTTS": np.mean((h > 0) & (a > 0)),
        "O25": np.mean((h + a) > 2.5),
        "Corn_Home": np.mean(hc),
        "Corn_Away": np.mean(ac),
        "Over9.5_Corn": np.mean((hc + ac) > 9.5),
        "Marcador": marcador_probable,
    }


def cuota_justa(probabilidad: float) -> str:
    return f"@{1 / probabilidad:.2f}" if probabilidad > 0 else "N/A"


def stake_kelly(probabilidad: float, cuota_decimal: float) -> float:
    b = cuota_decimal - 1
    q = 1 - probabilidad
    if b <= 0:
        return 0.0
    kelly = ((b * probabilidad) - q) / b
    return max(0.0, kelly)


def render_signal_card(titulo: str, probabilidad: float, subtitulo: str | None = None) -> None:
    es_value = probabilidad >= VALUE_BET_THRESHOLD
    clase = "signal-card value-bet" if es_value else "signal-card"
    tag = '<div class="signal-tag">VALUE BET DETECTADA</div>' if es_value else ""
    extra = f'<div class="signal-quote">{subtitulo}</div>' if subtitulo else ""
    st.markdown(
        f"""
        <div class="{clase}">
            <div class="signal-label">{titulo}</div>
            <div class="signal-value">{probabilidad * 100:.1f}%</div>
            {extra}
            {tag}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_corners_card(titulo: str, valor: float, subtitulo: str) -> None:
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
            <span>GF {stats['gf']:.2f} | GC {stats['gc']:.2f} | Córners For {stats['cf']:.2f} | Córners Concedidos {stats['cc']:.2f}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


inyectar_estilos()

st.markdown(
    """
    <div class="hero">
        <h1>Gordon BetScanner Pro</h1>
        <p>Terminal de trading deportivo con simulación Poisson, lectura de value y gestión de stake con Kelly.</p>
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
    visitante_default = 1 if len(equipos) > 1 else 0
    visitante = st.selectbox("Equipo visitante", equipos, index=visitante_default) if equipos else None
    escanear = st.button("ESCANEAR PARTIDO", use_container_width=True)

    st.caption("La simulación usa histórico reciente, localía y Poisson para estimar cuotas justas.")


if df is None:
    st.error("No se pudieron descargar los datos de la liga seleccionada.")
elif not equipos:
    st.warning("No hay equipos disponibles en la base cargada.")
elif escanear:
    if local == visitante:
        st.error("No puedes analizar al mismo equipo contra sí mismo.")
    else:
        with st.spinner("Ejecutando motor Poisson y calibrando mercados..."):
            stats_local = calcular_stats(df, local)
            stats_visitante = calcular_stats(df, visitante)

            if not stats_local or not stats_visitante:
                st.error("No hay datos suficientes para uno de los equipos seleccionados.")
            else:
                xg_l = (
                    (
                        (stats_local["gf"] * 0.4 + stats_local["gf_rec"] * 0.6)
                        + (stats_visitante["gc"] * 0.4 + stats_visitante["gc_rec"] * 0.6)
                    )
                    / 2
                ) * 1.12
                xg_v = (
                    (
                        (stats_visitante["gf"] * 0.4 + stats_visitante["gf_rec"] * 0.6)
                        + (stats_local["gc"] * 0.4 + stats_local["gc_rec"] * 0.6)
                    )
                    / 2
                )
                xc_l = ((stats_local["cf"] + stats_visitante["cc"]) / 2) * 1.15
                xc_v = (stats_visitante["cf"] + stats_local["cc"]) / 2

                res = simular_partido(xg_l, xg_v, xc_l, xc_v)

                st.success(f"Análisis completado: {local} vs {visitante}")

                top_left, top_right = st.columns([1.45, 1])

                with top_left:
                    st.markdown('<div class="section-title">Mercado 1X2</div>', unsafe_allow_html=True)
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        render_signal_card(f"Victoria {local}", res["1"], f"Cuota justa {cuota_justa(res['1'])}")
                    with c2:
                        render_signal_card("Empate", res["X"], f"Cuota justa {cuota_justa(res['X'])}")
                    with c3:
                        render_signal_card(f"Victoria {visitante}", res["2"], f"Cuota justa {cuota_justa(res['2'])}")

                    st.markdown('<div class="section-title">Mercado de Goles</div>', unsafe_allow_html=True)
                    c4, c5 = st.columns(2)
                    with c4:
                        render_signal_card("Ambos Marcan", res["BTTS"], f"Cuota justa {cuota_justa(res['BTTS'])}")
                    with c5:
                        render_signal_card("Over 2.5 Goles", res["O25"], f"Cuota justa {cuota_justa(res['O25'])}")

                    st.markdown('<div class="section-title">Mercado de Córners</div>', unsafe_allow_html=True)
                    c6, c7, c8 = st.columns(3)
                    with c6:
                        render_corners_card(f"Córners {local}", res["Corn_Home"], "Esperados")
                    with c7:
                        render_signal_card("Over 9.5 Córners", res["Over9.5_Corn"], "Probabilidad matemática")
                    with c8:
                        render_corners_card(f"Córners {visitante}", res["Corn_Away"], "Esperados")

                with top_right:
                    st.markdown('<div class="panel">', unsafe_allow_html=True)
                    st.markdown("### Radar del Partido")
                    st.metric("Marcador exacto más probable", res["Marcador"])
                    st.metric("xG Local estimado", f"{xg_l:.2f}")
                    st.metric("xG Visitante estimado", f"{xg_v:.2f}")
                    render_resumen_equipo(local, stats_local)
                    render_resumen_equipo(visitante, stats_visitante)
                    st.caption(
                        "Las señales en verde aparecen cuando la probabilidad supera el 65%, marcando una posible value bet."
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

                st.markdown('<div class="section-title">Calculadora de Stake (Criterio de Kelly)</div>', unsafe_allow_html=True)

                mercado_kelly = st.selectbox(
                    "Selecciona el mercado para calcular stake",
                    [
                        f"Victoria {local}",
                        "Empate",
                        f"Victoria {visitante}",
                        "Ambos Marcan",
                        "Over 2.5 Goles",
                        "Over 9.5 Córners",
                    ],
                )

                mapa_probabilidades = {
                    f"Victoria {local}": res["1"],
                    "Empate": res["X"],
                    f"Victoria {visitante}": res["2"],
                    "Ambos Marcan": res["BTTS"],
                    "Over 2.5 Goles": res["O25"],
                    "Over 9.5 Córners": res["Over9.5_Corn"],
                }

                prob_seleccionada = mapa_probabilidades[mercado_kelly]

                col_k1, col_k2 = st.columns(2)
                with col_k1:
                    cuota_usuario = st.number_input(
                        "Cuota ofrecida por la casa",
                        min_value=1.01,
                        value=max(1.05, round(1 / prob_seleccionada, 2)),
                        step=0.01,
                    )
                with col_k2:
                    bankroll = st.number_input(
                        "Bankroll disponible",
                        min_value=1.0,
                        value=100.0,
                        step=10.0,
                    )

                porcentaje_kelly = stake_kelly(prob_seleccionada, cuota_usuario)
                stake_recomendado = bankroll * porcentaje_kelly
                edge = (prob_seleccionada * cuota_usuario) - 1

                st.markdown(
                    f"""
                    <div class="kelly-box">
                        <div class="signal-label">Mercado seleccionado</div>
                        <div class="kelly-main">{mercado_kelly}</div>
                        <div class="kelly-sub">Probabilidad IA: {prob_seleccionada * 100:.2f}% | Cuota justa: {cuota_justa(prob_seleccionada)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                k1, k2, k3 = st.columns(3)
                k1.metric("% Bankroll a invertir", f"{porcentaje_kelly * 100:.2f}%")
                k2.metric("Stake recomendado", f"{stake_recomendado:.2f} u")
                k3.metric("Edge esperado", f"{edge * 100:.2f}%")

                if porcentaje_kelly > 0:
                    st.success(
                        "La cuota está por encima de la cuota justa. Según Kelly, existe ventaja matemática en este mercado."
                    )
                else:
                    st.warning(
                        "La cuota ofrecida no supera la cuota justa calculada. Kelly recomienda no invertir en esta selección."
                    )

                st.caption(
                    "Fórmula Kelly: f = ((cuota - 1) * p - (1 - p)) / (cuota - 1). Si el resultado es negativo, el stake recomendado es 0%."
                )
else:
    st.info("Configura el partido en la barra lateral y pulsa ESCANEAR PARTIDO para generar el reporte.")
