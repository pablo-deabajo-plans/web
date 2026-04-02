from __future__ import annotations

import pandas as pd
import streamlit as st

from core.model import VALUE_BET_THRESHOLD, cuota_justa
from data.sources import (
    extraer_contexto_mercado_espn,
    extraer_detalles_forma_espn,
    extraer_disponibilidad_espn,
    extraer_head_to_head_espn,
)
from data.teams import nombre_visual_equipo


def safe_key(texto: str) -> str:
    return (
        texto.lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("+", "plus")
        .replace("/", "_")
        .replace("-", "_")
    )


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
                max-width: 1500px;
                padding-top: 1.1rem;
                padding-bottom: 2.2rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .hero, .search-shell, .panel, .radar-card, .h2h-detail-card, .ranking-card, .trace-card {
                box-shadow: 0 18px 42px rgba(0, 0, 0, 0.16);
            }

            .hero {
                background: var(--bg-panel);
                border: 1px solid var(--line);
                border-radius: 24px;
                padding: 1.8rem;
                margin-bottom: 1.1rem;
            }

            .hero h1 { margin: 0; font-size: 2.35rem; color: #ffffff; }
            .hero p { margin: 0.55rem 0 0 0; color: var(--muted); font-size: 1rem; }

            .search-shell {
                background: rgba(7, 16, 29, 0.74);
                border: 1px solid rgba(96, 165, 250, 0.16);
                border-radius: 22px;
                padding: 1rem 1rem 0.25rem 1rem;
                margin-bottom: 1rem;
                backdrop-filter: blur(14px);
            }

            .search-shell h3 { color: #ffffff; margin: 0 0 0.2rem 0; font-size: 1.02rem; }
            .search-shell p { color: var(--muted); margin: 0 0 0.75rem 0; font-size: 0.9rem; }

            .section-title {
                margin: 1rem 0 0.8rem 0;
                font-size: 1rem;
                font-weight: 800;
                letter-spacing: 0.08em;
                color: #ffffff;
                text-transform: uppercase;
            }

            .panel, .radar-card, .h2h-detail-card, .ranking-card, .trace-card {
                background: var(--bg-card);
                border: 1px solid var(--line);
                border-radius: 22px;
                padding: 1.15rem;
            }

            .signal-card, .summary-chip, .split-card, .favorite-card, .fixture-card, .detail-card, .form-card, .h2h-card, .h2h-kpi {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                box-shadow: 0 14px 34px rgba(0, 0, 0, 0.12);
            }

            .signal-card {
                border-radius: 18px;
                padding: 1.05rem;
                min-height: 168px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
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

            .signal-value { font-size: 2rem; font-weight: 800; color: #ffffff; margin-top: 0.25rem; }
            .signal-quote { color: #9bd7ff; font-size: 0.95rem; margin-top: 0.35rem; }

            .signal-tag, .trace-tag {
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
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 0.85rem;
                margin: 0.7rem 0 1.15rem 0;
            }

            .summary-chip { border-radius: 18px; padding: 1rem 1.1rem; min-height: 108px; }
            .summary-chip strong { color: #ffffff; display: block; font-size: 1.1rem; }
            .summary-chip span { color: var(--muted); font-size: 0.86rem; }

            .split-card { border-radius: 18px; padding: 1rem; margin-bottom: 0.9rem; }
            .split-card h4 { color: #ffffff; margin: 0 0 0.65rem 0; }
            .split-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); gap: 0.6rem; }
            .mini-stat { border-radius: 14px; padding: 0.75rem 0.85rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); min-height: 86px; }
            .mini-stat strong { display: block; color: #ffffff; font-size: 0.96rem; }
            .mini-stat span { color: var(--muted); font-size: 0.82rem; }

            .odds-row, .odds-head {
                display: grid;
                grid-template-columns: 1.6fr 0.8fr 0.8fr 0.8fr 0.8fr;
                gap: 0.75rem;
                align-items: center;
            }

            .odds-row {
                padding: 0.9rem 1rem;
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.07);
                margin-bottom: 0.65rem;
                background: rgba(255,255,255,0.03);
            }

            .odds-row.value { border-color: rgba(0,229,168,0.45); background: linear-gradient(90deg, rgba(0,229,168,0.12), rgba(255,255,255,0.03)); }
            .odds-row.flat { border-color: rgba(59,130,246,0.45); background: linear-gradient(90deg, rgba(59,130,246,0.12), rgba(255,255,255,0.03)); }
            .odds-row.bad { border-color: rgba(255,107,107,0.35); background: linear-gradient(90deg, rgba(255,107,107,0.10), rgba(255,255,255,0.03)); }
            .odds-head { padding: 0 1rem 0.45rem 1rem; color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }

            .favorite-card { border-radius: 18px; padding: 1rem; margin-bottom: 0.8rem; }
            .favorite-card strong { color: #ffffff; font-size: 1rem; }
            .favorite-card p { color: var(--muted); margin: 0.35rem 0 0 0; font-size: 0.9rem; }

            .fixture-card, .detail-card, .form-card, .h2h-card { border-radius: 20px; padding: 1rem; }
            .fixture-card { min-height: 188px; margin-bottom: 0.85rem; }
            .fixture-card.active { border-color: rgba(0,229,168,0.45); background: linear-gradient(180deg, rgba(0,229,168,0.10), rgba(9,16,29,0.98)); box-shadow: 0 0 0 1px rgba(0,229,168,0.12), 0 22px 44px rgba(0, 0, 0, 0.2); }
            .fixture-meta, .form-head, .h2h-meta, .h2h-detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.75rem; }
            .fixture-meta { align-items: center; color: var(--muted); font-size: 0.82rem; margin-bottom: 0.7rem; }
            .fixture-teams { color: #ffffff; font-size: 1.06rem; font-weight: 800; line-height: 1.35; margin-bottom: 0.6rem; }
            .fixture-sub { color: var(--muted); font-size: 0.88rem; line-height: 1.45; }
            .source-pill { display: inline-block; padding: 0.24rem 0.58rem; border-radius: 999px; background: rgba(59,130,246,0.16); border: 1px solid rgba(59,130,246,0.24); color: #cfe3ff; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }

            .detail-card { margin-bottom: 0.85rem; min-height: 170px; }
            .detail-card h4, .radar-card h3, .insight-box h3, .ranking-card h3, .trace-card h3 { margin: 0 0 0.75rem 0; color: #ffffff; font-size: 1.05rem; }
            .detail-card p, .detail-card li { color: var(--muted); font-size: 0.9rem; margin: 0.3rem 0; }
            .detail-note { border-radius: 16px; padding: 0.9rem 1rem; background: rgba(255, 209, 102, 0.10); border: 1px solid rgba(255, 209, 102, 0.22); color: #fff4c2; margin-bottom: 0.8rem; }

            .radar-grid, .h2h-detail-grid, .trace-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 0.65rem; }
            .radar-stat, .h2h-kpi, .trace-kpi, .ranking-item { border-radius: 16px; padding: 0.85rem 0.9rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07); }
            .radar-stat span, .h2h-kpi span, .trace-kpi span { display: block; color: var(--muted); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.2rem; }
            .radar-stat strong, .h2h-kpi strong, .trace-kpi strong { color: #ffffff; font-size: 1rem; line-height: 1.35; }

            .insight-box { border-radius: 22px; padding: 1.15rem; background: linear-gradient(135deg, rgba(59,130,246,0.13), rgba(0,229,168,0.08)); border: 1px solid rgba(96, 165, 250, 0.2); height: 100%; }
            .insight-list { margin: 0; padding-left: 1rem; color: #d7e5fb; }
            .insight-list li { margin: 0 0 0.55rem 0; line-height: 1.45; }

            .form-card { min-height: 180px; }
            .form-head h4 { margin: 0.2rem 0 0 0; color: #ffffff; font-size: 1.1rem; }
            .form-ppg { min-width: 84px; text-align: right; color: #ffffff; font-size: 1.45rem; font-weight: 800; }
            .form-ppg span { display: block; color: var(--muted); font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; }
            .pill-row { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.9rem 0 0.8rem 0; }
            .result-chip { min-width: 34px; text-align: center; border-radius: 999px; padding: 0.3rem 0.6rem; font-size: 0.8rem; font-weight: 800; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04); color: #ffffff; }
            .result-chip.win { background: rgba(0,229,168,0.14); border-color: rgba(0,229,168,0.32); color: #ccfff1; }
            .result-chip.draw { background: rgba(255,209,102,0.16); border-color: rgba(255,209,102,0.34); color: #fff4c2; }
            .result-chip.loss { background: rgba(255,107,107,0.14); border-color: rgba(255,107,107,0.30); color: #ffd9d9; }
            .form-meta { display: flex; flex-wrap: wrap; gap: 0.55rem; color: var(--muted); font-size: 0.84rem; }
            .form-meta span { padding: 0.25rem 0.55rem; border-radius: 999px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); }

            .h2h-card { min-height: 190px; margin-bottom: 0.8rem; }
            .h2h-card.active { border-color: rgba(59,130,246,0.46); background: linear-gradient(180deg, rgba(59,130,246,0.12), rgba(9,16,29,0.98)); box-shadow: 0 0 0 1px rgba(59,130,246,0.12), 0 18px 40px rgba(0, 0, 0, 0.18); }
            .h2h-meta { color: var(--muted); font-size: 0.8rem; margin-bottom: 0.65rem; }
            .h2h-score { color: #ffffff; font-size: 1.2rem; font-weight: 800; line-height: 1.35; margin-bottom: 0.75rem; }
            .tag-pill { display: inline-block; margin-right: 0.4rem; margin-bottom: 0.4rem; padding: 0.26rem 0.58rem; border-radius: 999px; font-size: 0.76rem; font-weight: 700; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); color: #d8e7ff; }
            .h2h-detail-head p { margin: 0.2rem 0 0 0; color: var(--muted); font-size: 0.9rem; }

            .score-pill { display: inline-block; margin: 0 0.5rem 0.5rem 0; padding: 0.5rem 0.8rem; border-radius: 999px; background: rgba(59,130,246,0.14); border: 1px solid rgba(59,130,246,0.28); color: #e7f0ff; font-size: 0.86rem; font-weight: 700; }
            .kelly-box { border-radius: 20px; padding: 1.2rem; background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(0,229,168,0.08)); border: 1px solid rgba(96, 165, 250, 0.22); margin-top: 1rem; }
            .kelly-main { font-size: 1.7rem; font-weight: 800; color: #ffffff; }
            .kelly-sub { color: var(--muted); margin-top: 0.3rem; }

            .ranking-shell { display: grid; gap: 0.9rem; }
            .ranking-head { display: flex; justify-content: space-between; align-items: center; gap: 0.8rem; margin-bottom: 0.25rem; }
            .ranking-head-copy h3 { margin: 0; }
            .ranking-head-copy p { margin: 0.2rem 0 0 0; color: var(--muted); font-size: 0.92rem; }
            .ranking-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 110px; padding: 0.48rem 0.8rem; border-radius: 999px; background: rgba(0,229,168,0.12); border: 1px solid rgba(0,229,168,0.28); color: #cbfff2; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
            .ranking-top3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.75rem; }
            .ranking-spotlight { border-radius: 18px; padding: 1rem; border: 1px solid rgba(255,255,255,0.07); background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02)); min-height: 168px; }
            .ranking-spotlight.top-1 { border-color: rgba(0,229,168,0.34); box-shadow: inset 0 1px 0 rgba(255,255,255,0.04); }
            .ranking-rank { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.28rem 0.62rem; border-radius: 999px; background: rgba(59,130,246,0.14); color: #d9e8ff; font-size: 0.74rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
            .ranking-market { margin: 0.65rem 0 0.2rem 0; color: #ffffff; font-size: 1rem; font-weight: 800; line-height: 1.3; }
            .ranking-match { color: var(--muted); font-size: 0.9rem; line-height: 1.4; min-height: 2.5em; }
            .ranking-edge { margin: 0.9rem 0 0.2rem 0; color: #00e5a8; font-size: 1.7rem; font-weight: 900; line-height: 1; }
            .ranking-edge.negative { color: #ff8f8f; }
            .ranking-odds-meta { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.7rem; }
            .ranking-odds-meta span { padding: 0.28rem 0.56rem; border-radius: 999px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.07); color: var(--muted); font-size: 0.78rem; }
            .ranking-table { display: grid; gap: 0.55rem; }
            .ranking-row { display: grid; grid-template-columns: minmax(0, 2fr) minmax(120px, 0.8fr) repeat(3, minmax(90px, 0.6fr)); gap: 0.7rem; align-items: center; border-radius: 16px; padding: 0.78rem 0.9rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); }
            .ranking-row.header { background: rgba(59,130,246,0.10); border-color: rgba(96,165,250,0.20); color: #dcebff; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; }
            .ranking-cell-main strong { display: block; color: #ffffff; font-size: 0.95rem; line-height: 1.3; }
            .ranking-cell-main span { display: block; color: var(--muted); font-size: 0.82rem; margin-top: 0.14rem; }
            .ranking-pill { display: inline-flex; justify-content: center; align-items: center; padding: 0.36rem 0.56rem; border-radius: 999px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); color: #ffffff; font-size: 0.83rem; font-weight: 700; }
            .ranking-pill.edge-pos { background: rgba(0,229,168,0.12); border-color: rgba(0,229,168,0.26); color: #ccfff2; }
            .ranking-pill.edge-neg { background: rgba(255,107,107,0.12); border-color: rgba(255,107,107,0.26); color: #ffd4d4; }
            .ranking-provider { color: var(--muted); font-size: 0.8rem; text-align: right; }
            .ranking-footer-note { color: var(--muted); font-size: 0.82rem; margin-top: 0.1rem; }
            .trace-grid { margin-top: 0.75rem; }
            .trace-subtitle { color: #ffffff; font-size: 0.95rem; font-weight: 700; margin: 0.9rem 0 0.45rem 0; }

            .stTabs [data-baseweb="tab-list"] { gap: 0.4rem; flex-wrap: wrap; }
            .stTabs [data-baseweb="tab"] { background: rgba(255,255,255,0.04); border-radius: 14px; padding: 0.55rem 0.9rem; color: var(--muted); }
            .stTabs [aria-selected="true"] { background: linear-gradient(90deg, rgba(0,229,168,0.18), rgba(59,130,246,0.18)); color: #ffffff; }

            div[data-testid="stMetric"] { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07); border-radius: 16px; padding: 0.8rem; min-height: 110px; box-shadow: 0 12px 30px rgba(0, 0, 0, 0.10); }
            div[data-baseweb="select"] > div, div[data-testid="stDateInput"] input, div[data-testid="stNumberInput"] input { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.10); border-radius: 16px; }
            div[data-testid="stDataFrame"] { border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; overflow: hidden; }
            .stButton > button { border-radius: 14px; border: none; background: linear-gradient(90deg, #00e5a8, #3b82f6); color: #03111d; font-weight: 800; min-height: 3rem; }

            @media (max-width: 1100px) {
                .hero h1 { font-size: 2rem; }
                .summary-band { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .odds-row, .odds-head { grid-template-columns: 1.4fr repeat(4, minmax(0, 1fr)); }
                .ranking-top3 { grid-template-columns: 1fr; }
                .ranking-row { grid-template-columns: minmax(0, 1.6fr) minmax(105px, 0.75fr) repeat(3, minmax(82px, 0.5fr)); gap: 0.55rem; }
            }

            @media (max-width: 780px) {
                .block-container { padding-left: 0.7rem; padding-right: 0.7rem; }
                div[data-testid="stHorizontalBlock"] { gap: 0.7rem; }
                div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
                .hero, .search-shell, .h2h-detail-card, .radar-card, .panel, .trace-card, .ranking-card { padding: 1rem; }
                .hero h1 { font-size: 1.7rem; }
                .summary-band { grid-template-columns: 1fr; }
                .signal-card, .fixture-card, .form-card, .detail-card, .h2h-card { min-height: unset; }
                .h2h-detail-head, .form-head, .fixture-meta { flex-direction: column; align-items: flex-start; }
                .ranking-head { align-items: flex-start; flex-direction: column; }
                .ranking-row, .ranking-row.header { grid-template-columns: 1fr; }
                .ranking-provider { text-align: left; }
                .ranking-market { margin-top: 0.55rem; }
                .ranking-edge { font-size: 1.45rem; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def render_radar_panel(analisis: dict) -> None:
    resultado = analisis["resultado"]
    st.markdown(
        f"""
        <div class="radar-card">
            <h3>Radar instantaneo</h3>
            <div class="radar-grid">
                <div class="radar-stat"><span>Marcador probable</span><strong>{resultado['Marcador']}</strong></div>
                <div class="radar-stat"><span>xG local</span><strong>{analisis['xg_local']:.2f}</strong></div>
                <div class="radar-stat"><span>xG visitante</span><strong>{analisis['xg_visitante']:.2f}</strong></div>
                <div class="radar-stat"><span>Corners esperados</span><strong>{resultado['Total_Corners']:.2f}</strong></div>
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


def render_insight_panel(insights: list[str]) -> None:
    items_html = "".join(f"<li>{insight}</li>" for insight in insights)
    st.markdown(
        f"""
        <div class="insight-box">
            <h3>Lectura tactica del cruce</h3>
            <ul class="insight-list">{items_html}</ul>
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
    titulo_lista = "Tarjetas de partidos de hoy" if fecha_objetivo == hoy else f"Tarjetas de partidos del {fecha_objetivo.strftime('%d/%m/%Y')}"
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
                        <div class="fixture-teams">{nombre_visual_equipo(partido.get('HomeTeam', 'TBD'))}<br>vs<br>{nombre_visual_equipo(partido.get('AwayTeam', 'TBD'))}</div>
                        <div class="fixture-sub">Abre este panel para ver lectura del modelo, comparativa, mercado y detalles en vivo.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Panel cargado" if seleccion_actual else "Ver estadisticas",
                    key=f"fixture_{safe_key(partido['FixtureLabel'])}_{inicio}",
                    use_container_width=True,
                    disabled=seleccion_actual,
                ):
                    st.session_state["fixture_label"] = partido["FixtureLabel"]
                    st.rerun()
    seleccion_fixture = st.session_state.get("fixture_label")
    return partidos[partidos["FixtureLabel"] == seleccion_fixture].iloc[0]


def render_contexto_feed_espn(resumen: dict, analisis: dict) -> None:
    if not resumen:
        st.markdown('<div class="detail-note">No hay feed enriquecido disponible para este partido. El panel sigue funcionando con el modelo historico y las cuotas manuales.</div>', unsafe_allow_html=True)
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
        st.markdown(
            f'<div class="detail-note">La fuente abierta del partido no expone ahora mismo {", ".join(avisos)}. Cuando el feed no lo trae, la app lo marca como no disponible en lugar de inventarlo.</div>',
            unsafe_allow_html=True,
        )

    top_left, top_mid, top_right = st.columns(3)
    with top_left:
        lineas = []
        if contexto_mercado["available"]:
            lineas.append(f"<p>Proveedor: {contexto_mercado['provider']}</p>")
            lineas.append(f"<p>Mercado: {contexto_mercado['details']}</p>")
            if contexto_mercado["home_ml"] is not None:
                texto = f"1 local: ML {contexto_mercado['home_ml']}"
                if contexto_mercado["home_decimal"] is not None:
                    texto += f" | Decimal @{contexto_mercado['home_decimal']:.2f}"
                lineas.append(f"<p>{texto}</p>")
            if contexto_mercado["draw_ml"] is not None:
                texto = f"X empate: ML {contexto_mercado['draw_ml']}"
                if contexto_mercado["draw_decimal"] is not None:
                    texto += f" | Decimal @{contexto_mercado['draw_decimal']:.2f}"
                lineas.append(f"<p>{texto}</p>")
            if contexto_mercado["away_ml"] is not None:
                texto = f"2 visitante: ML {contexto_mercado['away_ml']}"
                if contexto_mercado["away_decimal"] is not None:
                    texto += f" | Decimal @{contexto_mercado['away_decimal']:.2f}"
                lineas.append(f"<p>{texto}</p>")
            if contexto_mercado["over_under"] is not None:
                lineas.append(f"<p>Linea total: {contexto_mercado['over_under']:.2f}</p>")
        else:
            lineas.append("<p>Sin cuotas abiertas en este feed.</p>")
        st.markdown(f'<div class="detail-card"><h4>Mercado en tiempo real</h4>{"".join(lineas)}</div>', unsafe_allow_html=True)

    with top_mid:
        lineas = []
        lineas.append("<p>El feed abierto puede o no traer alineaciones reales segun liga y evento.</p>")
        lineas.append("<p>Alineaciones: disponibles.</p>" if disponibilidad["lineups"] else "<p>Alineaciones confirmadas/probables no disponibles.</p>")
        lineas.append("<p>Lesiones/sanciones: detectadas.</p>" if disponibilidad["injuries"] else "<p>Lesiones y sanciones no publicadas en este feed.</p>")
        st.markdown(f'<div class="detail-card"><h4>Alineaciones y bajas</h4>{"".join(lineas)}</div>', unsafe_allow_html=True)

    with top_right:
        lineas = []
        lineas.append("<p>El feed trae referencias a xG o shot map para este partido.</p>" if disponibilidad["xg_shots"] else "<p>No hay xG shot-by-shot en abierto para este evento.</p>")
        lineas.append(f"<p>xG estimado del modelo: {analisis['local']} {analisis['xg_local']:.2f} | {analisis['visitante']} {analisis['xg_visitante']:.2f}</p>")
        lineas.append("<p>El motor prepartido usa temporada, casa/fuera, forma y H2H.</p>")
        st.markdown(f'<div class="detail-card"><h4>xG por disparo</h4>{"".join(lineas)}</div>', unsafe_allow_html=True)

    bottom_left, bottom_right = st.columns(2)
    with bottom_left:
        lineas = [f"<p>{entrada['team']}: {entrada['summary']}</p>" for entrada in forma_espn] or ["<p>Sin resumen de forma extra en la fuente abierta.</p>"]
        st.markdown(f'<div class="detail-card"><h4>Lectura de forma del feed</h4>{"".join(lineas)}</div>', unsafe_allow_html=True)
    with bottom_right:
        lineas = [f"<p>{item}</p>" for item in h2h_espn] or ["<p>Sin head to head adicional en el feed abierto.</p>"]
        if contexto_mercado["pickcenter"]:
            lineas.append("<p>Consenso del mercado:</p>")
            for pick in contexto_mercado["pickcenter"]:
                detalle = pick.get("details") or pick.get("summary") or "Sin detalle"
                lineas.append(f"<p>- {detalle}</p>")
        st.markdown(f'<div class="detail-card"><h4>Head to head del feed</h4>{"".join(lineas)}</div>', unsafe_allow_html=True)


def render_form_card(team: str, form: dict) -> None:
    resultado_clase = {"W": "win", "D": "draw", "L": "loss"}
    resultados_html = "".join(
        f"<span class='result-chip {resultado_clase.get(resultado, '')}'>{resultado}</span>"
        for resultado in (form.get("results") or ["-"])
    )
    st.markdown(
        f"""
        <div class="form-card">
            <div class="form-head">
                <div><div class="signal-label">Forma reciente</div><h4>{team}</h4></div>
                <div class="form-ppg">{form['ppg']:.2f}<span>PPG</span></div>
            </div>
            <div class="pill-row">{resultados_html}</div>
            <div class="form-meta">
                <span>{form['wins']}V {form['draws']}E {form['losses']}D</span>
                <span>{form['points']} pts</span>
                <span>DG {form['goal_diff']:+d}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def formatear_duelo(home_valor: float | None, away_valor: float | None, decimales: int = 0) -> str | None:
    if home_valor is None and away_valor is None:
        return None

    def _fmt(valor: float | None) -> str:
        if valor is None:
            return "-"
        if decimales == 0:
            return str(int(round(valor)))
        return f"{valor:.{decimales}f}"

    return f"{_fmt(home_valor)} | {_fmt(away_valor)}"


def render_h2h_summary_card(h2h: dict, local: str, visitante: str) -> None:
    st.markdown(
        f"""
        <div class="form-card">
            <div class="form-head">
                <div><div class="signal-label">Resumen H2H</div><h4>{local} vs {visitante}</h4></div>
                <div class="form-ppg">{h2h['matches']}<span>Partidos</span></div>
            </div>
            <div class="pill-row">
                <span class="tag-pill">{local}: {h2h['local_wins']}</span>
                <span class="tag-pill">Empates: {h2h['draws']}</span>
                <span class="tag-pill">{visitante}: {h2h['away_wins']}</span>
            </div>
            <div class="form-meta">
                <span>Media goles {h2h['avg_total_goals']:.2f}</span>
                <span>BTTS {h2h['btts_pct'] * 100:.1f}%</span>
                <span>Over 2.5 {h2h['over25_pct'] * 100:.1f}%</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_h2h_explorer(h2h: dict) -> None:
    partidos = h2h.get("recent_matches", [])
    if not partidos:
        st.caption("No se detectaron cruces directos recientes entre ambos en la base historica cargada.")
        return
    ids = [partido["id"] for partido in partidos]
    if st.session_state.get("selected_h2h_match") not in ids:
        st.session_state["selected_h2h_match"] = ids[0]
    st.markdown("### Ultimos enfrentamientos")
    st.caption("Pincha cualquier cruce para abrir sus estadisticas historicas debajo.")
    for inicio in range(0, len(partidos), 2):
        bloque = partidos[inicio : inicio + 2]
        cols = st.columns(2)
        for col, partido in zip(cols, bloque):
            activo = st.session_state.get("selected_h2h_match") == partido["id"]
            clase = "h2h-card active" if activo else "h2h-card"
            tags_html = "".join(
                f"<span class='tag-pill'>{etiqueta}</span>"
                for etiqueta in ["BTTS" if partido["btts"] else "No BTTS", "Over 2.5" if partido["over25"] else "Under 2.5"]
            )
            with col:
                st.markdown(
                    f"""
                    <div class="{clase}">
                        <div class="h2h-meta"><span>{partido['date']}</span><span>{partido['winner']}</span></div>
                        <div class="h2h-score">{partido['home_team']} {partido['home_score']} - {partido['away_score']} {partido['away_team']}</div>
                        <div>{tags_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Partido abierto" if activo else "Ver estadisticas",
                    key=f"open_h2h_{partido['id']}",
                    use_container_width=True,
                    disabled=activo,
                ):
                    st.session_state["selected_h2h_match"] = partido["id"]
                    st.rerun()
    seleccionado = next(partido for partido in partidos if partido["id"] == st.session_state.get("selected_h2h_match"))
    st.markdown(
        f"""
        <div class="h2h-detail-card">
            <div class="h2h-detail-head">
                <div><h4>{seleccionado['home_team']} vs {seleccionado['away_team']}</h4><p>{seleccionado['date']} | Ganador: {seleccionado['winner']}</p></div>
                <div class="signal-tag">H2H Explorer</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    tarjetas = [
        ("Marcador", f"{seleccionado['home_score']} - {seleccionado['away_score']}"),
        ("Corners", formatear_duelo(seleccionado["corners_home"], seleccionado["corners_away"])),
        ("Tiros", formatear_duelo(seleccionado["shots_home"], seleccionado["shots_away"])),
        ("Tiros a puerta", formatear_duelo(seleccionado["shots_on_target_home"], seleccionado["shots_on_target_away"])),
        ("Amarillas", formatear_duelo(seleccionado["yellow_home"], seleccionado["yellow_away"])),
        ("Rojas", formatear_duelo(seleccionado["red_home"], seleccionado["red_away"])),
        ("Bet365 1", None if seleccionado["odds_home"] is None else f"@{seleccionado['odds_home']:.2f}"),
        ("Bet365 X", None if seleccionado["odds_draw"] is None else f"@{seleccionado['odds_draw']:.2f}"),
        ("Bet365 2", None if seleccionado["odds_away"] is None else f"@{seleccionado['odds_away']:.2f}"),
    ]
    visibles = [(titulo, valor) for titulo, valor in tarjetas if valor is not None]
    for inicio in range(0, len(visibles), 4):
        bloque = visibles[inicio : inicio + 4]
        cols = st.columns(len(bloque))
        for col, (titulo, valor) in zip(cols, bloque):
            with col:
                st.markdown(f'<div class="h2h-kpi"><span>{titulo}</span><strong>{valor}</strong></div>', unsafe_allow_html=True)


def tabla_comparativa(local: str, visitante: str, local_home: dict, visitante_away: dict, local_all: dict, visitante_all: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Metric": "GF escenario", f"{local} casa": round(local_home["gf"], 2), f"{visitante} fuera": round(visitante_away["gf"], 2), "Diff local-away": round(local_home["gf"] - visitante_away["gf"], 2)},
            {"Metric": "GC escenario", f"{local} casa": round(local_home["gc"], 2), f"{visitante} fuera": round(visitante_away["gc"], 2), "Diff local-away": round(local_home["gc"] - visitante_away["gc"], 2)},
            {"Metric": "Corners for escenario", f"{local} casa": round(local_home["corners_for"], 2), f"{visitante} fuera": round(visitante_away["corners_for"], 2), "Diff local-away": round(local_home["corners_for"] - visitante_away["corners_for"], 2)},
            {"Metric": "BTTS escenario", f"{local} casa": round(local_home["btts_pct"] * 100, 1), f"{visitante} fuera": round(visitante_away["btts_pct"] * 100, 1), "Diff local-away": round((local_home["btts_pct"] - visitante_away["btts_pct"]) * 100, 1)},
            {"Metric": "Over 2.5 escenario", f"{local} casa": round(local_home["over25_pct"] * 100, 1), f"{visitante} fuera": round(visitante_away["over25_pct"] * 100, 1), "Diff local-away": round((local_home["over25_pct"] - visitante_away["over25_pct"]) * 100, 1)},
        ]
    )


def render_traceability_panel(analisis: dict) -> None:
    trace = analisis["trace"]
    st.markdown('<div class="trace-card"><h3>Trazabilidad del modelo</h3><p>La proyeccion no sale de una caja negra: aqui ves los inputs ponderados que empujan el xG de cada lado.</p></div>', unsafe_allow_html=True)
    for bloque_titulo, datos in [("xG local", trace["local_xg"]), ("xG visitante", trace["visitante_xg"])]:
        st.markdown(f'<div class="trace-subtitle">{bloque_titulo}</div>', unsafe_allow_html=True)
        filas = "".join(
            f'<div class="trace-kpi"><span>{item["group"]}</span><strong>{item["label"]}: {item["value"]:.2f} x {item["weight"]:.2f}</strong></div>'
            for item in datos["components"]
        )
        st.markdown(f'<div class="trace-grid">{filas}</div>', unsafe_allow_html=True)
        resumen = [
            ("Ataque base", f"{datos['base_attack']:.2f}"),
            ("Defensa base", f"{datos['base_defense']:.2f}"),
            ("Boost local", f"{datos['home_boost']:.2f}"),
            ("Ajuste forma", f"{datos['form_adjustment']:+.3f}"),
            ("Ajuste H2H", f"{datos['h2h_adjustment']:+.3f}"),
            ("xG final", f"{datos['final_xg']:.2f}"),
        ]
        st.markdown(
            "<div class='trace-grid'>"
            + "".join(f"<div class='trace-kpi'><span>{titulo}</span><strong>{valor}</strong></div>" for titulo, valor in resumen)
            + "</div>",
            unsafe_allow_html=True,
        )


def render_ranking_value_panel(ranking: list[dict], fecha_label: str) -> None:
    st.markdown('<div class="section-title">Ranking de Value Bets del dia</div>', unsafe_allow_html=True)
    if not ranking:
        st.info("No hay cuotas abiertas suficientes para construir el ranking automatico en esta fecha.")
        return
    top_items = ranking[:3]
    rest_items = ranking[3:8]
    badge_label = f"{len(ranking)} picks" if len(ranking) != 1 else "1 pick"

    spotlight_html = ""
    for idx, fila in enumerate(top_items, start=1):
        edge_pct = fila["edge"] * 100
        edge_class = "negative" if edge_pct < 0 else ""
        spotlight_html += f"""
        <div class="ranking-spotlight {'top-1' if idx == 1 else ''}">
            <div class="ranking-rank">Top {idx}</div>
            <div class="ranking-market">{fila['market']}</div>
            <div class="ranking-match">{fila['match']}</div>
            <div class="ranking-edge {edge_class}">{edge_pct:+.2f}%</div>
            <div class="ranking-odds-meta">
                <span>Prob IA {fila['prob'] * 100:.1f}%</span>
                <span>Justa @{fila['fair_odds']:.2f}</span>
                <span>Casa @{fila['offered_odds']:.2f}</span>
            </div>
        </div>
        """

    table_rows = ""
    for fila in rest_items:
        edge_pct = fila["edge"] * 100
        edge_class = "edge-pos" if edge_pct >= 0 else "edge-neg"
        table_rows += f"""
        <div class="ranking-row">
            <div class="ranking-cell-main">
                <strong>{fila['match']}</strong>
                <span>{fila['market']}</span>
            </div>
            <div><span class="ranking-pill {edge_class}">{edge_pct:+.2f}%</span></div>
            <div><span class="ranking-pill">@{fila['offered_odds']:.2f}</span></div>
            <div><span class="ranking-pill">@{fila['fair_odds']:.2f}</span></div>
            <div class="ranking-provider">{fila['provider']}</div>
        </div>
        """

    table_block = ""
    if table_rows:
        table_block = f"""
        <div class="ranking-table">
            <div class="ranking-row header">
                <div>Partido y mercado</div>
                <div>Edge</div>
                <div>Casa</div>
                <div>Justa</div>
                <div>Fuente</div>
            </div>
            {table_rows}
        </div>
        """

    st.markdown(
        f"""
        <div class="ranking-card">
            <div class="ranking-shell">
                <div class="ranking-head">
                    <div class="ranking-head-copy">
                        <h3>Top edges de {fecha_label}</h3>
                        <p>Vista resumida de las oportunidades con mayor diferencia entre la cuota de mercado y la cuota justa del modelo.</p>
                    </div>
                    <div class="ranking-badge">{badge_label}</div>
                </div>
                <div class="ranking-top3">
                    {spotlight_html}
                </div>
                {table_block}
                <div class="ranking-footer-note">El panel prioriza claridad visual: destaca el top 3 y resume el resto para no ocupar media pantalla.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
