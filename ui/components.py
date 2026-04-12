from __future__ import annotations

import textwrap

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


def inyectar_estilos_clasico() -> None:
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
            .ranking-subtable { margin-top: 0.35rem; }
            .ranking-subhead { display: grid; grid-template-columns: minmax(0, 2.2fr) repeat(4, minmax(0, 1fr)); gap: 0.7rem; padding: 0 0.2rem 0.35rem 0.2rem; color: #dcebff; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; }
            .ranking-row-card { border-radius: 16px; padding: 0.85rem 0.95rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); margin-bottom: 0.55rem; }
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
                .ranking-subhead { grid-template-columns: minmax(0, 1.8fr) repeat(4, minmax(0, 1fr)); gap: 0.55rem; }
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
                .ranking-subhead { display: none; }
                .ranking-provider { text-align: left; }
                .ranking-market { margin-top: 0.55rem; }
                .ranking-edge { font-size: 1.45rem; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inyectar_estilos() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg: #0f1724;
                --bg-2: #172234;
                --panel: rgba(19, 29, 46, 0.88);
                --panel-soft: rgba(24, 36, 56, 0.78);
                --card: rgba(27, 40, 63, 0.92);
                --card-2: rgba(21, 31, 49, 0.95);
                --ink: #f7fafc;
                --muted: #a7b5c9;
                --line: rgba(148, 163, 184, 0.18);
                --accent: #f59e0b;
                --accent-2: #38bdf8;
                --accent-3: #22c55e;
                --good: #34d399;
                --bad: #f87171;
                --shadow: 0 22px 48px rgba(4, 10, 20, 0.34);
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(56,189,248,0.16), transparent 26%),
                    radial-gradient(circle at top right, rgba(245,158,11,0.12), transparent 22%),
                    linear-gradient(180deg, #0b1320 0%, #111a29 100%);
                color: var(--ink);
            }

            .stApp::before {
                content: "";
                position: fixed;
                inset: 0;
                pointer-events: none;
                background-image:
                    linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
                background-size: 28px 28px;
                mask-image: radial-gradient(circle at center, black 45%, transparent 100%);
                opacity: 0.45;
            }

            .block-container {
                max-width: 1480px;
                padding-top: 1.15rem;
                padding-bottom: 2.3rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .masthead, .control-deck, .panel, .radar-card, .h2h-detail-card, .ranking-card, .trace-card {
                border-radius: 26px;
                box-shadow: var(--shadow);
            }

            .masthead {
                background:
                    linear-gradient(135deg, rgba(21,31,49,0.98), rgba(16,24,39,0.96)),
                    var(--panel);
                border: 1px solid rgba(148, 163, 184, 0.16);
                padding: 1.45rem;
                margin-bottom: 1.05rem;
                position: relative;
                overflow: hidden;
            }

            .masthead::after {
                content: "";
                position: absolute;
                right: -70px;
                top: -55px;
                width: 260px;
                height: 260px;
                border-radius: 50%;
                background: radial-gradient(circle, rgba(56,189,248,0.22), rgba(56,189,248,0.04) 58%, transparent 74%);
                pointer-events: none;
            }

            .masthead-grid {
                display: grid;
                grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
                gap: 1rem;
                align-items: stretch;
            }

            .masthead-copy {
                background:
                    linear-gradient(160deg, rgba(245,158,11,0.10), rgba(255,255,255,0.02)),
                    rgba(13, 21, 35, 0.56);
                border: 1px solid rgba(148, 163, 184, 0.14);
                border-radius: 24px;
                padding: 1.6rem;
            }

            .masthead-kicker {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.4rem 0.78rem;
                border-radius: 999px;
                background: rgba(245,158,11,0.12);
                border: 1px solid rgba(245,158,11,0.18);
                color: #ffd79a;
                font-size: 0.75rem;
                font-weight: 900;
                letter-spacing: 0.1em;
                text-transform: uppercase;
            }

            .masthead-copy h1 {
                margin: 0.8rem 0 0 0;
                color: var(--ink);
                font-size: 2.75rem;
                line-height: 0.92;
                letter-spacing: -0.04em;
            }

            .masthead-copy p {
                margin: 0.95rem 0 0 0;
                color: #c3cfdd;
                font-size: 1rem;
                line-height: 1.68;
                max-width: 62ch;
            }

            .masthead-rail {
                display: grid;
                grid-template-columns: 1fr;
                gap: 0.75rem;
            }

            .masthead-panel {
                background: linear-gradient(180deg, rgba(22,33,52,0.96), rgba(17,26,42,0.96));
                border: 1px solid rgba(148, 163, 184, 0.14);
                border-radius: 20px;
                padding: 1rem;
                min-height: 126px;
            }

            .masthead-panel h3 {
                margin: 0;
                color: #98a8be;
                font-size: 0.78rem;
                letter-spacing: 0.09em;
                text-transform: uppercase;
            }

            .masthead-panel strong {
                display: block;
                margin-top: 0.6rem;
                color: var(--ink);
                font-size: 1.15rem;
                line-height: 1.2;
            }

            .masthead-panel p {
                margin: 0.45rem 0 0 0;
                color: var(--muted);
                font-size: 0.88rem;
                line-height: 1.55;
            }

            .chip-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.55rem;
                margin-top: 1.05rem;
            }

            .masthead-chip {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.48rem 0.78rem;
                border-radius: 999px;
                background: rgba(56,189,248,0.10);
                border: 1px solid rgba(56,189,248,0.16);
                color: #d8f2ff;
                font-size: 0.8rem;
                font-weight: 800;
            }

            .control-deck {
                background: linear-gradient(180deg, rgba(21,31,49,0.92), rgba(16,24,39,0.90));
                border: 1px solid rgba(148, 163, 184, 0.14);
                padding: 1rem 1rem 0.2rem 1rem;
                margin-bottom: 1rem;
                backdrop-filter: blur(12px);
            }

            .control-deck h3 {
                margin: 0;
                color: var(--ink);
                font-size: 1rem;
            }

            .control-deck p {
                margin: 0.3rem 0 0.75rem 0;
                color: var(--muted);
                font-size: 0.9rem;
            }

            .section-title {
                margin: 1rem 0 0.8rem 0;
                padding-left: 0.85rem;
                border-left: 4px solid var(--accent-2);
                font-size: 0.92rem;
                font-weight: 900;
                letter-spacing: 0.1em;
                color: var(--ink);
                text-transform: uppercase;
            }

            .panel, .radar-card, .h2h-detail-card, .ranking-card, .trace-card {
                background: linear-gradient(180deg, rgba(24,36,56,0.96), rgba(18,28,45,0.96));
                border: 1px solid rgba(148, 163, 184, 0.14);
                padding: 1.15rem;
            }

            .signal-card, .summary-chip, .split-card, .favorite-card, .fixture-card, .detail-card, .form-card, .h2h-card, .h2h-kpi {
                background: linear-gradient(180deg, rgba(34,49,74,0.92), rgba(24,36,58,0.94));
                border: 1px solid rgba(148, 163, 184, 0.12);
                box-shadow: 0 12px 28px rgba(4, 10, 20, 0.18);
            }

            .signal-card {
                border-radius: 20px;
                padding: 1.05rem;
                min-height: 168px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }

            .signal-card.value-bet {
                border-color: rgba(52,211,153,0.26);
                background: linear-gradient(180deg, rgba(52,211,153,0.14), rgba(22,32,52,0.96));
                box-shadow: 0 0 0 1px rgba(52,211,153,0.06), 0 16px 32px rgba(4, 10, 20, 0.22);
            }

            .signal-label {
                color: var(--muted);
                font-size: 0.8rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }

            .signal-value { font-size: 2rem; font-weight: 900; color: var(--ink); margin-top: 0.25rem; }
            .signal-quote { color: #b8e8ff; font-size: 0.95rem; margin-top: 0.35rem; }

            .signal-tag, .trace-tag {
                display: inline-block;
                margin-top: 0.7rem;
                padding: 0.3rem 0.65rem;
                border-radius: 999px;
                font-size: 0.76rem;
                font-weight: 900;
                color: #0b1320;
                background: var(--accent);
            }

            .summary-band {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 0.85rem;
                margin: 0.7rem 0 1.15rem 0;
            }

            .summary-chip { border-radius: 20px; padding: 1rem 1.1rem; min-height: 108px; }
            .summary-chip strong { color: var(--ink); display: block; font-size: 1.08rem; }
            .summary-chip span { color: var(--muted); font-size: 0.86rem; }

            .split-card { border-radius: 20px; padding: 1rem; margin-bottom: 0.9rem; }
            .split-card h4 { color: var(--ink); margin: 0 0 0.65rem 0; }
            .split-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); gap: 0.6rem; }
            .mini-stat { border-radius: 16px; padding: 0.78rem 0.85rem; background: rgba(13,21,35,0.34); border: 1px solid rgba(148,163,184,0.10); min-height: 86px; }
            .mini-stat strong { display: block; color: var(--ink); font-size: 0.96rem; }
            .mini-stat span { color: var(--muted); font-size: 0.82rem; }

            .odds-row, .odds-head {
                display: grid;
                grid-template-columns: 1.6fr 0.8fr 0.8fr 0.8fr 0.8fr;
                gap: 0.75rem;
                align-items: center;
            }

            .odds-row {
                padding: 0.9rem 1rem;
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                margin-bottom: 0.65rem;
                background: rgba(18, 28, 45, 0.54);
            }

            .odds-row.value { border-color: rgba(52,211,153,0.22); background: linear-gradient(90deg, rgba(52,211,153,0.12), rgba(18,28,45,0.54)); }
            .odds-row.flat { border-color: rgba(56,189,248,0.20); background: linear-gradient(90deg, rgba(56,189,248,0.10), rgba(18,28,45,0.54)); }
            .odds-row.bad { border-color: rgba(248,113,113,0.22); background: linear-gradient(90deg, rgba(248,113,113,0.10), rgba(18,28,45,0.54)); }
            .odds-head { padding: 0 1rem 0.45rem 1rem; color: var(--muted); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.08em; }

            .favorite-card { border-radius: 20px; padding: 1rem; margin-bottom: 0.8rem; }
            .favorite-card strong { color: var(--ink); font-size: 1rem; }
            .favorite-card p { color: var(--muted); margin: 0.35rem 0 0 0; font-size: 0.9rem; }

            .fixture-card, .detail-card, .form-card, .h2h-card { border-radius: 22px; padding: 1rem; }
            .fixture-card { min-height: 188px; margin-bottom: 0.85rem; }
            .fixture-card.active { border-color: rgba(245,158,11,0.26); background: linear-gradient(180deg, rgba(245,158,11,0.12), rgba(24,36,58,0.96)); box-shadow: 0 0 0 1px rgba(245,158,11,0.06), 0 18px 34px rgba(4, 10, 20, 0.22); }
            .fixture-meta, .form-head, .h2h-meta, .h2h-detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.75rem; }
            .fixture-meta { align-items: center; color: var(--muted); font-size: 0.82rem; margin-bottom: 0.7rem; }
            .fixture-teams { color: var(--ink); font-size: 1.08rem; font-weight: 900; line-height: 1.35; margin-bottom: 0.6rem; }
            .fixture-sub { color: var(--muted); font-size: 0.88rem; line-height: 1.45; }
            .source-pill { display: inline-block; padding: 0.24rem 0.58rem; border-radius: 999px; background: rgba(56,189,248,0.10); border: 1px solid rgba(56,189,248,0.18); color: #bde9ff; font-size: 0.74rem; font-weight: 800; letter-spacing: 0.04em; text-transform: uppercase; }

            .detail-card { margin-bottom: 0.85rem; min-height: 170px; }
            .detail-card h4, .radar-card h3, .insight-box h3, .ranking-card h3, .trace-card h3 { margin: 0 0 0.75rem 0; color: var(--ink); font-size: 1.03rem; }
            .detail-card p, .detail-card li { color: var(--muted); font-size: 0.9rem; margin: 0.3rem 0; }
            .detail-note { border-radius: 16px; padding: 0.9rem 1rem; background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.20); color: #ffe0a6; margin-bottom: 0.8rem; }

            .radar-grid, .h2h-detail-grid, .trace-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 0.65rem; }
            .radar-stat, .h2h-kpi, .trace-kpi, .ranking-item { border-radius: 16px; padding: 0.85rem 0.9rem; background: rgba(14,22,37,0.42); border: 1px solid rgba(148,163,184,0.10); }
            .radar-stat span, .h2h-kpi span, .trace-kpi span { display: block; color: var(--muted); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.2rem; }
            .radar-stat strong, .h2h-kpi strong, .trace-kpi strong { color: var(--ink); font-size: 1rem; line-height: 1.35; }

            .insight-box { border-radius: 22px; padding: 1.15rem; background: linear-gradient(135deg, rgba(56,189,248,0.10), rgba(245,158,11,0.08)); border: 1px solid rgba(148,163,184,0.12); height: 100%; }
            .insight-list { margin: 0; padding-left: 1rem; color: #d9e5f3; }
            .insight-list li { margin: 0 0 0.55rem 0; line-height: 1.45; }

            .form-card { min-height: 180px; }
            .form-head h4 { margin: 0.2rem 0 0 0; color: var(--ink); font-size: 1.1rem; }
            .form-ppg { min-width: 84px; text-align: right; color: var(--ink); font-size: 1.45rem; font-weight: 900; }
            .form-ppg span { display: block; color: var(--muted); font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; }
            .pill-row { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.9rem 0 0.8rem 0; }
            .result-chip { min-width: 34px; text-align: center; border-radius: 999px; padding: 0.3rem 0.6rem; font-size: 0.8rem; font-weight: 900; border: 1px solid rgba(148,163,184,0.12); background: rgba(14,22,37,0.42); color: var(--ink); }
            .result-chip.win { background: rgba(52,211,153,0.14); border-color: rgba(52,211,153,0.22); color: #b8ffe4; }
            .result-chip.draw { background: rgba(245,158,11,0.12); border-color: rgba(245,158,11,0.20); color: #ffd79a; }
            .result-chip.loss { background: rgba(248,113,113,0.12); border-color: rgba(248,113,113,0.18); color: #ffd1d1; }
            .form-meta { display: flex; flex-wrap: wrap; gap: 0.55rem; color: var(--muted); font-size: 0.84rem; }
            .form-meta span { padding: 0.25rem 0.55rem; border-radius: 999px; background: rgba(14,22,37,0.42); border: 1px solid rgba(148,163,184,0.10); }

            .h2h-card { min-height: 190px; margin-bottom: 0.8rem; }
            .h2h-card.active { border-color: rgba(56,189,248,0.22); background: linear-gradient(180deg, rgba(56,189,248,0.10), rgba(24,36,58,0.95)); box-shadow: 0 0 0 1px rgba(56,189,248,0.06), 0 16px 30px rgba(4, 10, 20, 0.20); }
            .h2h-meta { color: var(--muted); font-size: 0.8rem; margin-bottom: 0.65rem; }
            .h2h-score { color: var(--ink); font-size: 1.2rem; font-weight: 900; line-height: 1.35; margin-bottom: 0.75rem; }
            .tag-pill { display: inline-block; margin-right: 0.4rem; margin-bottom: 0.4rem; padding: 0.26rem 0.58rem; border-radius: 999px; font-size: 0.76rem; font-weight: 800; background: rgba(14,22,37,0.42); border: 1px solid rgba(148,163,184,0.10); color: #e4edf7; }
            .h2h-detail-head p { margin: 0.2rem 0 0 0; color: var(--muted); font-size: 0.9rem; }

            .score-pill { display: inline-block; margin: 0 0.5rem 0.5rem 0; padding: 0.5rem 0.8rem; border-radius: 999px; background: rgba(56,189,248,0.10); border: 1px solid rgba(56,189,248,0.16); color: #d6f2ff; font-size: 0.84rem; font-weight: 800; }
            .kelly-box { border-radius: 22px; padding: 1.2rem; background: linear-gradient(135deg, rgba(245,158,11,0.10), rgba(56,189,248,0.08)); border: 1px solid rgba(148,163,184,0.12); margin-top: 1rem; }
            .kelly-main { font-size: 1.7rem; font-weight: 900; color: var(--ink); }
            .kelly-sub { color: var(--muted); margin-top: 0.3rem; }

            .ranking-shell { display: grid; gap: 0.9rem; }
            .ranking-head { display: flex; justify-content: space-between; align-items: center; gap: 0.8rem; margin-bottom: 0.25rem; }
            .ranking-head-copy h3 { margin: 0; }
            .ranking-head-copy p { margin: 0.2rem 0 0 0; color: var(--muted); font-size: 0.92rem; }
            .ranking-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 110px; padding: 0.48rem 0.8rem; border-radius: 999px; background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.18); color: #ffd79a; font-size: 0.78rem; font-weight: 900; letter-spacing: 0.06em; text-transform: uppercase; }
            .ranking-top3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.75rem; }
            .ranking-spotlight { border-radius: 20px; padding: 1rem; border: 1px solid rgba(148,163,184,0.12); background: rgba(18, 28, 45, 0.56); min-height: 168px; }
            .ranking-spotlight.top-1 { border-color: rgba(245,158,11,0.22); }
            .ranking-rank { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.28rem 0.62rem; border-radius: 999px; background: rgba(56,189,248,0.10); color: #d6f2ff; font-size: 0.74rem; font-weight: 900; letter-spacing: 0.06em; text-transform: uppercase; }
            .ranking-market { margin: 0.65rem 0 0.2rem 0; color: var(--ink); font-size: 1rem; font-weight: 900; line-height: 1.3; }
            .ranking-match { color: var(--muted); font-size: 0.9rem; line-height: 1.4; min-height: 2.5em; }
            .ranking-edge { margin: 0.9rem 0 0.2rem 0; color: var(--good); font-size: 1.7rem; font-weight: 900; line-height: 1; }
            .ranking-edge.negative { color: var(--bad); }
            .ranking-odds-meta { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.7rem; }
            .ranking-odds-meta span { padding: 0.28rem 0.56rem; border-radius: 999px; background: rgba(14,22,37,0.42); border: 1px solid rgba(148,163,184,0.10); color: var(--muted); font-size: 0.78rem; }
            .ranking-subtable { margin-top: 0.35rem; }
            .ranking-subhead { display: grid; grid-template-columns: minmax(0, 2.2fr) repeat(4, minmax(0, 1fr)); gap: 0.7rem; padding: 0 0.2rem 0.35rem 0.2rem; color: var(--muted); font-size: 0.74rem; font-weight: 900; letter-spacing: 0.05em; text-transform: uppercase; }
            .ranking-row-card { border-radius: 18px; padding: 0.85rem 0.95rem; background: rgba(18, 28, 45, 0.56); border: 1px solid rgba(148,163,184,0.10); margin-bottom: 0.55rem; }
            .ranking-cell-main strong { display: block; color: var(--ink); font-size: 0.95rem; line-height: 1.3; }
            .ranking-cell-main span { display: block; color: var(--muted); font-size: 0.82rem; margin-top: 0.14rem; }
            .ranking-pill { display: inline-flex; justify-content: center; align-items: center; padding: 0.36rem 0.56rem; border-radius: 999px; background: rgba(14,22,37,0.42); border: 1px solid rgba(148,163,184,0.10); color: var(--ink); font-size: 0.83rem; font-weight: 800; }
            .ranking-pill.edge-pos { background: rgba(52,211,153,0.12); border-color: rgba(52,211,153,0.18); color: #b8ffe4; }
            .ranking-pill.edge-neg { background: rgba(248,113,113,0.12); border-color: rgba(248,113,113,0.18); color: #ffd1d1; }
            .ranking-provider { color: var(--muted); font-size: 0.8rem; text-align: right; }
            .ranking-footer-note { color: var(--muted); font-size: 0.82rem; margin-top: 0.1rem; }
            .trace-grid { margin-top: 0.75rem; }
            .trace-subtitle { color: var(--ink); font-size: 0.95rem; font-weight: 800; margin: 0.9rem 0 0.45rem 0; }

            .stTabs [data-baseweb="tab-list"] { gap: 0.45rem; flex-wrap: wrap; }
            .stTabs [data-baseweb="tab"] {
                background: rgba(18, 28, 45, 0.62);
                border-radius: 999px;
                border: 1px solid rgba(148,163,184,0.10);
                padding: 0.52rem 0.95rem;
                color: var(--muted);
            }
            .stTabs [aria-selected="true"] {
                background: linear-gradient(90deg, rgba(245,158,11,0.18), rgba(56,189,248,0.16));
                color: var(--ink);
                border-color: rgba(245,158,11,0.22);
            }

            div[data-testid="stMetric"] {
                background: linear-gradient(180deg, rgba(30,43,67,0.90), rgba(21,31,49,0.90));
                border: 1px solid rgba(148,163,184,0.12);
                border-radius: 18px;
                padding: 0.85rem;
                min-height: 110px;
                box-shadow: 0 10px 24px rgba(4, 10, 20, 0.18);
            }

            div[data-baseweb="select"] > div,
            div[data-testid="stDateInput"] input,
            div[data-testid="stNumberInput"] input {
                background: rgba(18, 28, 45, 0.86);
                border: 1px solid rgba(148,163,184,0.16);
                border-radius: 16px;
                color: #e7eef8;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid rgba(148,163,184,0.12);
                border-radius: 20px;
                overflow: hidden;
            }

            .stButton > button {
                border-radius: 16px;
                border: 1px solid rgba(245,158,11,0.16);
                background: linear-gradient(90deg, #f59e0b, #f97316);
                color: #0b1320;
                font-weight: 900;
                min-height: 3rem;
                box-shadow: 0 10px 24px rgba(249,115,22,0.20);
                transition: transform 140ms ease, box-shadow 140ms ease, filter 140ms ease;
            }

            .stButton > button:hover {
                transform: translateY(-1px);
                box-shadow: 0 14px 28px rgba(249,115,22,0.26);
                filter: saturate(1.08);
            }

            @media (max-width: 1100px) {
                .masthead-grid { grid-template-columns: 1fr; }
                .masthead-copy h1 { font-size: 2.2rem; }
                .summary-band { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .odds-row, .odds-head { grid-template-columns: 1.4fr repeat(4, minmax(0, 1fr)); }
                .ranking-top3 { grid-template-columns: 1fr; }
                .ranking-subhead { grid-template-columns: minmax(0, 1.8fr) repeat(4, minmax(0, 1fr)); gap: 0.55rem; }
            }

            @media (max-width: 780px) {
                .block-container { padding-left: 0.7rem; padding-right: 0.7rem; }
                div[data-testid="stHorizontalBlock"] { gap: 0.7rem; }
                div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
                .masthead, .control-deck, .h2h-detail-card, .radar-card, .panel, .trace-card, .ranking-card { padding: 1rem; }
                .masthead-copy { padding: 1.1rem; }
                .masthead-copy h1 { font-size: 1.9rem; }
                .masthead-rail { grid-template-columns: 1fr; }
                .summary-band { grid-template-columns: 1fr; }
                .signal-card, .fixture-card, .form-card, .detail-card, .h2h-card { min-height: unset; }
                .h2h-detail-head, .form-head, .fixture-meta, .ranking-head { flex-direction: column; align-items: flex-start; }
                .ranking-subhead { display: none; }
                .ranking-provider { text-align: left; }
                .ranking-edge { font-size: 1.45rem; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inyectar_estilos() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg: #ffffff;
                --surface: #ffffff;
                --surface-alt: #f5f5f5;
                --ink: #000000;
                --muted: #444444;
                --line: #d9d9d9;
            }

            .stApp,
            .stApp [data-testid="stAppViewContainer"],
            .stApp [data-testid="stHeader"] {
                background: var(--bg);
                color: var(--ink);
            }

            .block-container {
                max-width: 1480px;
                padding-top: 1.15rem;
                padding-bottom: 2rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .masthead,
            .control-deck,
            .panel,
            .radar-card,
            .h2h-detail-card,
            .ranking-card,
            .trace-card,
            .signal-card,
            .summary-chip,
            .split-card,
            .favorite-card,
            .fixture-card,
            .detail-card,
            .form-card,
            .h2h-card,
            .h2h-kpi,
            .ranking-spotlight,
            .ranking-row-card,
            .insight-box,
            .kelly-box,
            .mini-stat,
            .radar-stat,
            .trace-kpi,
            .ranking-item,
            div[data-testid="stMetric"] {
                background: var(--surface);
                color: var(--ink);
                border: 1px solid var(--line);
                border-radius: 0;
                box-shadow: none;
            }

            .masthead,
            .control-deck,
            .panel,
            .radar-card,
            .h2h-detail-card,
            .ranking-card,
            .trace-card,
            .signal-card,
            .summary-chip,
            .split-card,
            .favorite-card,
            .fixture-card,
            .detail-card,
            .form-card,
            .h2h-card,
            .insight-box,
            .kelly-box {
                padding: 1rem;
            }

            .masthead-grid,
            .split-grid,
            .radar-grid,
            .h2h-detail-grid,
            .trace-grid,
            .summary-band,
            .ranking-top3 {
                display: grid;
                gap: 0.75rem;
            }

            .masthead-grid {
                grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
                align-items: stretch;
            }

            .masthead-copy,
            .masthead-panel {
                background: var(--surface);
                border: 1px solid var(--line);
                border-radius: 0;
                padding: 1rem;
            }

            .masthead-kicker,
            .masthead-chip,
            .source-pill,
            .tag-pill,
            .score-pill,
            .signal-tag,
            .trace-tag,
            .ranking-badge,
            .ranking-rank,
            .ranking-pill,
            .result-chip,
            .form-meta span,
            .ranking-odds-meta span {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0.3rem 0.6rem;
                border: 1px solid #000000;
                border-radius: 0;
                background: #ffffff;
                color: #000000;
                font-weight: 800;
            }

            .masthead-copy h1,
            .masthead-panel strong,
            .control-deck h3,
            .detail-card h4,
            .radar-card h3,
            .insight-box h3,
            .ranking-card h3,
            .trace-card h3,
            .fixture-teams,
            .h2h-score,
            .signal-value,
            .kelly-main,
            .ranking-market,
            .summary-chip strong,
            .ranking-cell-main strong,
            .mini-stat strong,
            .radar-stat strong,
            .h2h-kpi strong,
            .trace-kpi strong {
                color: var(--ink);
            }

            .masthead-copy p,
            .masthead-panel h3,
            .masthead-panel p,
            .control-deck p,
            .signal-label,
            .signal-quote,
            .summary-chip span,
            .mini-stat span,
            .detail-card p,
            .detail-card li,
            .fixture-meta,
            .fixture-sub,
            .h2h-meta,
            .h2h-detail-head p,
            .form-meta,
            .ranking-head-copy p,
            .ranking-match,
            .ranking-provider,
            .ranking-footer-note,
            .trace-subtitle,
            .odds-head,
            .radar-stat span,
            .h2h-kpi span,
            .trace-kpi span {
                color: var(--muted);
            }

            .fixture-sub,
            .source-pill {
                display: none !important;
            }

            .chip-row,
            .pill-row,
            .ranking-odds-meta,
            .form-meta {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
            }

            .section-title {
                margin: 1rem 0 0.8rem 0;
                padding-left: 0.75rem;
                border-left: 4px solid #000000;
                color: var(--ink);
                font-size: 0.92rem;
                font-weight: 900;
                text-transform: uppercase;
            }

            .summary-band {
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                margin: 0.7rem 0 1rem 0;
            }

            .split-grid,
            .radar-grid,
            .h2h-detail-grid,
            .trace-grid {
                grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
            }

            .odds-row,
            .odds-head,
            .ranking-subhead {
                display: grid;
                grid-template-columns: 1.6fr 0.8fr 0.8fr 0.8fr 0.8fr;
                gap: 0.75rem;
                align-items: center;
            }

            .odds-row,
            .ranking-row-card,
            .ranking-spotlight {
                background: var(--surface);
                border: 1px solid var(--line);
            }

            .signal-card.value-bet,
            .fixture-card.active,
            .h2h-card.active,
            .odds-row.value,
            .odds-row.flat,
            .odds-row.bad,
            .ranking-spotlight.top-1,
            .ranking-pill.edge-pos,
            .ranking-pill.edge-neg,
            .result-chip.win,
            .result-chip.draw,
            .result-chip.loss,
            .detail-note {
                background: var(--surface-alt);
                border-color: #000000;
                color: var(--ink);
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.45rem;
                flex-wrap: wrap;
            }

            .stTabs [data-baseweb="tab"] {
                background: #ffffff;
                border: 1px solid var(--line);
                border-radius: 0;
                color: var(--ink);
                padding: 0.5rem 0.9rem;
            }

            .stTabs [aria-selected="true"] {
                border-color: #000000;
                background: var(--surface-alt);
                color: var(--ink);
            }

            div[data-baseweb="select"] > div,
            div[data-testid="stDateInput"] input,
            div[data-testid="stNumberInput"] input {
                background: #ffffff;
                border: 1px solid var(--line);
                border-radius: 0;
                color: #000000;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid var(--line);
                border-radius: 0;
                overflow: hidden;
            }

            .stButton > button {
                min-height: 3rem;
                border: 1px solid #000000;
                border-radius: 0;
                background: #ffffff;
                color: #000000;
                box-shadow: none;
                font-weight: 800;
            }

            .stButton > button:hover {
                background: #f2f2f2;
                color: #000000;
                border-color: #000000;
            }

            @media (max-width: 1100px) {
                .masthead-grid { grid-template-columns: 1fr; }
                .summary-band { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .ranking-top3 { grid-template-columns: 1fr; }
            }

            @media (max-width: 780px) {
                .block-container { padding-left: 0.7rem; padding-right: 0.7rem; }
                div[data-testid="stHorizontalBlock"] { gap: 0.7rem; }
                div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
                .summary-band { grid-template-columns: 1fr; }
                .h2h-detail-head,
                .form-head,
                .fixture-meta,
                .ranking-head {
                    flex-direction: column;
                    align-items: flex-start;
                }
                .ranking-subhead { display: none; }
                .ranking-provider { text-align: left; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inyectar_estilos() -> None:
    st.markdown(
        """
        <style>
            :root {
                color-scheme: dark;
                --bg: #0B1220;
                --bg-2: #111827;
                --card: #1F2937;
                --hover: #374151;
                --green: #22C55E;
                --green-light: #4ADE80;
                --green-dark: #16A34A;
                --blue: #3B82F6;
                --blue-light: #60A5FA;
                --blue-dark: #2563EB;
                --warning: #F59E0B;
                --danger: #EF4444;
                --info: #06B6D4;
                --title: #F9FAFB;
                --subtitle: #D1D5DB;
                --body: #9CA3AF;
                --muted: #6B7280;
                --inverse: #111827;
                --border: #374151;
                --divider: #1F2937;
            }

            html,
            body {
                background: #0B1220 !important;
                color: #F9FAFB !important;
                color-scheme: dark !important;
            }

            .stApp,
            .stApp [data-testid="stAppViewContainer"],
            .stApp [data-testid="stHeader"] {
                background:
                    radial-gradient(circle at top right, rgba(59,130,246,0.16), transparent 28%),
                    radial-gradient(circle at top left, rgba(34,197,94,0.12), transparent 24%),
                    linear-gradient(180deg, var(--bg) 0%, var(--bg-2) 100%);
                color: var(--title);
            }

            input,
            textarea,
            select,
            button {
                color-scheme: dark;
            }

            .block-container {
                max-width: 1520px;
                padding-top: 1rem;
                padding-bottom: 2.2rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .titlebar,
            .panel,
            .radar-card,
            .h2h-detail-card,
            .ranking-card,
            .trace-card,
            .signal-card,
            .summary-chip,
            .split-card,
            .favorite-card,
            .fixture-card,
            .fixture-table-head,
            .fixture-table-row,
            .detail-card,
            .form-card,
            .h2h-card,
            .h2h-kpi,
            .ranking-spotlight,
            .ranking-row-card,
            .insight-box,
            .kelly-box,
            .mini-stat,
            .radar-stat,
            .trace-kpi,
            .ranking-item,
            div[data-testid="stMetric"] {
                background: rgba(31, 41, 55, 0.92);
                border: 1px solid var(--border);
                border-radius: 18px;
                box-shadow: 0 18px 44px rgba(0, 0, 0, 0.22);
                color: var(--title);
            }

            .titlebar {
                padding: 1.1rem 1.25rem;
                margin-bottom: 0.85rem;
                background: linear-gradient(135deg, rgba(17,24,39,0.98), rgba(31,41,55,0.96));
            }

            .titlebar-copy h1 {
                margin: 0;
                color: var(--title);
                font-size: 2.65rem;
                line-height: 1;
                letter-spacing: -0.04em;
            }

            .titlebar-copy p {
                margin: 0.35rem 0 0 0;
                color: var(--subtitle);
                font-size: 0.98rem;
                line-height: 1.45;
            }

            .layout-divider {
                height: 1px;
                background: linear-gradient(90deg, transparent, rgba(55,65,81,0.85), transparent);
                margin: 0.25rem 0 1rem 0;
            }

            .toolbar-shell,
            .league-card,
            .league-summary-card,
            .odds-panel,
            .empty-panel,
            .search-result-card,
            .player-api-card,
            .player-prop-card {
                background: rgba(17, 24, 39, 0.78);
                border: 1px solid var(--border);
                border-radius: 18px;
                box-shadow: 0 18px 44px rgba(0, 0, 0, 0.18);
            }

            .toolbar-shell {
                padding: 1rem 1.1rem;
                margin-bottom: 0.85rem;
                background: linear-gradient(135deg, rgba(17,24,39,0.96), rgba(31,41,55,0.88));
            }

            .toolbar-kicker,
            .league-card-country,
            .league-card-foot,
            .odds-note,
            .odds-summary-card span,
            .empty-panel p {
                color: var(--body);
                font-size: 0.88rem;
            }

            .toolbar-kicker,
            .league-card-country {
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 800;
            }

            .toolbar-title,
            .league-card-title,
            .odds-market,
            .empty-panel h3 {
                color: var(--title);
                font-weight: 900;
            }

            .toolbar-title {
                margin-top: 0.2rem;
                font-size: 1.45rem;
                line-height: 1.1;
            }

            .toolbar-meta {
                margin-top: 0.35rem;
                color: var(--subtitle);
                font-size: 0.95rem;
            }

            .league-summary-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 0.75rem;
                margin: 0 0 1rem 0;
            }

            .league-summary-card {
                padding: 0.95rem 1rem;
            }

            .league-summary-card strong {
                display: block;
                color: var(--title);
                font-size: 1.65rem;
                line-height: 1;
                margin-top: 0.3rem;
            }

            .league-card {
                padding: 1rem 1.05rem;
                min-height: 196px;
                background: linear-gradient(180deg, rgba(31,41,55,0.92), rgba(17,24,39,0.92));
            }

            .league-card-top {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 0.75rem;
            }

            .league-card-title {
                font-size: 1.1rem;
                line-height: 1.2;
            }

            .league-rank-pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 68px;
                padding: 0.28rem 0.6rem;
                border-radius: 999px;
                border: 1px solid rgba(59,130,246,0.28);
                background: rgba(59,130,246,0.12);
                color: var(--title);
                font-size: 0.74rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .league-card-count {
                margin-top: 1.2rem;
                color: var(--title);
                font-size: 2.6rem;
                font-weight: 900;
                line-height: 1;
            }

            .league-card-count-label {
                margin-top: 0.3rem;
                color: var(--subtitle);
                font-size: 0.94rem;
                font-weight: 700;
            }

            .league-card-foot {
                margin-top: 1rem;
                padding-top: 0.8rem;
                border-top: 1px solid rgba(55, 65, 81, 0.9);
                line-height: 1.45;
            }

            .empty-panel {
                padding: 1.15rem;
            }

            .empty-panel h3 {
                margin: 0 0 0.35rem 0;
                font-size: 1.2rem;
            }

            .empty-panel p {
                margin: 0;
                line-height: 1.55;
            }

            .search-results-shell {
                margin: 0.35rem 0 1rem 0;
            }

            .search-icon-spacer {
                height: 1.55rem;
            }

            .search-result-card {
                padding: 0.82rem 0.95rem;
                min-height: 74px;
                background: rgba(17, 24, 39, 0.9);
                box-shadow: none;
                margin-bottom: 0.55rem;
            }

            .search-result-card strong {
                display: block;
                color: var(--title);
                font-size: 0.98rem;
                line-height: 1.3;
            }

            .search-result-card span {
                display: block;
                margin-top: 0.16rem;
                color: var(--body);
                font-size: 0.84rem;
                line-height: 1.45;
            }

            .search-result-meta {
                text-align: center;
            }

            .player-api-card,
            .player-prop-card {
                padding: 1rem 1.05rem;
            }

            .player-api-card {
                margin-bottom: 0.9rem;
                background: linear-gradient(135deg, rgba(59,130,246,0.12), rgba(17,24,39,0.92));
            }

            .player-api-card h3,
            .player-prop-card h4 {
                margin: 0;
                color: var(--title);
            }

            .player-api-card p,
            .player-prop-card p {
                margin: 0.35rem 0 0 0;
                color: var(--body);
                line-height: 1.5;
            }

            .player-prop-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 0.75rem;
                margin-top: 0.75rem;
            }

            .player-prop-card span {
                display: inline-flex;
                margin-top: 0.6rem;
                padding: 0.3rem 0.6rem;
                border-radius: 999px;
                border: 1px solid rgba(59,130,246,0.28);
                background: rgba(59,130,246,0.12);
                color: var(--title);
                font-size: 0.78rem;
                font-weight: 800;
            }

            .summary-band,
            .split-grid,
            .radar-grid,
            .h2h-detail-grid,
            .trace-grid,
            .ranking-top3 {
                display: grid;
                gap: 0.75rem;
            }

            .summary-band {
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                margin: 0 0 1rem 0;
            }

            .split-grid,
            .radar-grid,
            .h2h-detail-grid,
            .trace-grid {
                grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
            }

            .signal-card,
            .summary-chip,
            .split-card,
            .favorite-card,
            .fixture-card,
            .detail-card,
            .form-card,
            .h2h-card,
            .h2h-detail-card,
            .radar-card,
            .ranking-card,
            .trace-card,
            .insight-box,
            .kelly-box {
                padding: 1rem;
            }

            .section-title {
                margin: 0 0 0.8rem 0;
                padding-left: 0.85rem;
                border-left: 4px solid var(--green);
                color: var(--title);
                font-size: 0.92rem;
                font-weight: 900;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .signal-label,
            .summary-chip span,
            .mini-stat span,
            .detail-card p,
            .detail-card li,
            .fixture-meta,
            .h2h-meta,
            .h2h-detail-head p,
            .form-meta,
            .ranking-head-copy p,
            .ranking-match,
            .ranking-provider,
            .trace-subtitle,
            .odds-head,
            .radar-stat span,
            .h2h-kpi span,
            .trace-kpi span,
            .fixture-table-cell,
            .fixture-table-match span {
                color: var(--body);
            }

            .masthead-kicker,
            .tag-pill,
            .score-pill,
            .signal-tag,
            .trace-tag,
            .ranking-badge,
            .ranking-rank,
            .ranking-pill,
            .result-chip,
            .form-meta span,
            .ranking-odds-meta span {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0.32rem 0.62rem;
                border-radius: 999px;
                border: 1px solid rgba(74, 222, 128, 0.22);
                background: rgba(34, 197, 94, 0.12);
                color: var(--title);
                font-weight: 800;
            }

            .signal-value,
            .kelly-main,
            .ranking-market,
            .summary-chip strong,
            .ranking-cell-main strong,
            .mini-stat strong,
            .radar-stat strong,
            .h2h-kpi strong,
            .trace-kpi strong,
            .fixture-teams,
            .h2h-score,
            .detail-card h4,
            .radar-card h3,
            .insight-box h3,
            .ranking-card h3,
            .trace-card h3 {
                color: var(--title);
            }

            .fixture-card,
            .ranking-spotlight,
            .ranking-row-card,
            .odds-row,
            .fixture-table-row {
                background: rgba(17, 24, 39, 0.74);
            }

            .fixture-table-block {
                background: rgba(17, 24, 39, 0.74);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 0.8rem 0.95rem;
                min-height: 72px;
            }

            .fixture-card.active,
            .h2h-card.active,
            .ranking-spotlight.top-1,
            .signal-card.value-bet,
            .fixture-table-row.active {
                border-color: rgba(34, 197, 94, 0.9);
                background: linear-gradient(135deg, rgba(34,197,94,0.16), rgba(31,41,55,0.92));
            }

            .fixture-table-block.active {
                border-color: rgba(34, 197, 94, 0.9);
                background: linear-gradient(135deg, rgba(34,197,94,0.16), rgba(31,41,55,0.92));
            }

            .fixture-card { min-height: 170px; }
            .fixture-teams { font-size: 1.08rem; font-weight: 800; line-height: 1.45; }

            .fixture-table-head,
            .fixture-table-row {
                display: grid;
                grid-template-columns: minmax(120px, 0.9fr) minmax(0, 2.2fr) minmax(150px, 0.8fr);
                gap: 0.75rem;
                align-items: center;
                padding: 0.8rem 0.95rem;
                margin-bottom: 0.45rem;
            }

            .fixture-table-head {
                background: rgba(17, 24, 39, 0.64);
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-size: 0.76rem;
                color: var(--subtitle);
            }

            .fixture-table-match strong {
                display: block;
                color: var(--title);
                font-size: 0.96rem;
                line-height: 1.35;
            }

            .odds-head {
                display: grid;
                grid-template-columns: 1.6fr 0.8fr 0.8fr 0.8fr 0.8fr;
                gap: 0.75rem;
                align-items: center;
            }

            .odds-panel {
                padding: 1rem;
                margin-top: 0.35rem;
                background: linear-gradient(180deg, rgba(31,41,55,0.92), rgba(17,24,39,0.94));
            }

            .odds-panel-head {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 1rem;
                margin-bottom: 0.85rem;
            }

            .odds-panel-head h3 {
                margin: 0;
                color: var(--title);
                font-size: 1.1rem;
            }

            .odds-panel-head p {
                margin: 0.25rem 0 0 0;
                color: var(--body);
                font-size: 0.9rem;
            }

            .odds-overview {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 0.7rem;
                margin-bottom: 0.95rem;
            }

            .odds-summary-card {
                padding: 0.85rem 0.9rem;
                border-radius: 16px;
                border: 1px solid rgba(55, 65, 81, 0.95);
                background: rgba(17, 24, 39, 0.78);
            }

            .odds-summary-card strong {
                display: block;
                color: var(--title);
                font-size: 1.25rem;
                line-height: 1.15;
                margin-top: 0.18rem;
            }

            .odds-list {
                display: grid;
                gap: 0.75rem;
            }

            .odds-row {
                display: block;
                padding: 1rem;
                border-radius: 18px;
                border: 1px solid rgba(55, 65, 81, 0.95);
                background: rgba(17, 24, 39, 0.82);
            }

            .odds-row.value {
                border-color: rgba(34, 197, 94, 0.55);
                background: linear-gradient(135deg, rgba(34,197,94,0.14), rgba(17,24,39,0.92));
            }

            .odds-row.flat {
                border-color: rgba(59,130,246,0.5);
                background: linear-gradient(135deg, rgba(59,130,246,0.12), rgba(17,24,39,0.92));
            }

            .odds-row.bad {
                border-color: rgba(239,68,68,0.45);
                background: linear-gradient(135deg, rgba(239,68,68,0.10), rgba(17,24,39,0.92));
            }

            .odds-row-top {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 0.85rem;
            }

            .odds-market {
                font-size: 1rem;
                line-height: 1.2;
            }

            .odds-note {
                margin-top: 0.3rem;
                line-height: 1.45;
            }

            .odds-badge {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 92px;
                padding: 0.42rem 0.72rem;
                border-radius: 999px;
                font-size: 0.86rem;
                font-weight: 900;
                line-height: 1;
                color: var(--title);
            }

            .odds-badge.value {
                background: rgba(34,197,94,0.18);
                border: 1px solid rgba(34,197,94,0.42);
            }

            .odds-badge.flat {
                background: rgba(59,130,246,0.18);
                border: 1px solid rgba(59,130,246,0.42);
            }

            .odds-badge.bad {
                background: rgba(239,68,68,0.18);
                border: 1px solid rgba(239,68,68,0.38);
            }

            .odds-metrics {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.6rem;
                margin-top: 0.9rem;
            }

            .odds-metric {
                padding: 0.75rem 0.8rem;
                border-radius: 14px;
                border: 1px solid rgba(55, 65, 81, 0.85);
                background: rgba(31, 41, 55, 0.74);
            }

            .odds-metric span {
                display: block;
                color: var(--body);
                font-size: 0.76rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .odds-metric strong {
                display: block;
                color: var(--title);
                font-size: 1rem;
                margin-top: 0.18rem;
            }

            .ranking-subhead {
                display: grid;
                grid-template-columns: 1.8fr 0.8fr 0.8fr 0.8fr;
                gap: 0.75rem;
                align-items: center;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.5rem;
                flex-wrap: wrap;
                margin-bottom: 0.3rem;
            }

            .stTabs [data-baseweb="tab"] {
                background: rgba(17, 24, 39, 0.86);
                border: 1px solid var(--border);
                border-radius: 999px;
                color: var(--body);
                padding: 0.52rem 0.95rem;
            }

            .stTabs [aria-selected="true"] {
                background: rgba(59,130,246,0.18);
                border-color: var(--blue);
                color: var(--title);
            }

            div[data-testid="stRadio"] > div {
                gap: 0.55rem;
            }

            div[data-testid="stRadio"] label {
                background: rgba(17, 24, 39, 0.86);
                border: 1px solid var(--border);
                border-radius: 999px;
                padding: 0.55rem 0.95rem;
                min-height: auto;
            }

            div[data-testid="stRadio"] label p {
                color: var(--body);
                font-weight: 700;
                margin: 0;
            }

            div[data-testid="stRadio"] label:has(input:checked) {
                background: rgba(59,130,246,0.18);
                border-color: var(--blue);
            }

            div[data-testid="stRadio"] label:has(input:checked) p {
                color: var(--title);
            }

            div[data-baseweb="select"] > div,
            div[data-testid="stDateInput"] input,
            div[data-testid="stNumberInput"] input {
                background: rgba(17, 24, 39, 0.92);
                border: 1px solid var(--border);
                border-radius: 14px;
                color: var(--title);
            }

            div[data-testid="stMetric"] {
                min-height: 108px;
                padding: 0.8rem 0.9rem;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid var(--border);
                border-radius: 16px;
                overflow: hidden;
            }

            .stButton > button {
                min-height: 2.9rem;
                border-radius: 14px;
                border: 1px solid var(--green-dark);
                background: linear-gradient(90deg, var(--green-dark), var(--green));
                color: var(--title);
                box-shadow: none;
                font-weight: 800;
            }

            .stButton > button:hover {
                background: linear-gradient(90deg, var(--green), var(--green-light));
                border-color: var(--green-light);
                color: var(--title);
            }

            @media (max-width: 1100px) {
                .summary-band { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .ranking-top3 { grid-template-columns: 1fr; }
                .odds-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            }

            @media (max-width: 780px) {
                .block-container { padding-left: 0.7rem; padding-right: 0.7rem; }
                div[data-testid="stHorizontalBlock"] { gap: 0.7rem; }
                div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
                .summary-band { grid-template-columns: 1fr; }
                .fixture-table-head,
                .fixture-table-row {
                    grid-template-columns: 1fr;
                }
                .h2h-detail-head,
                .form-head,
                .fixture-meta,
                .ranking-head,
                .odds-panel-head,
                .odds-row-top,
                .league-card-top {
                    flex-direction: column;
                    align-items: flex-start;
                }
                .ranking-subhead { display: none; }
                .odds-metrics { grid-template-columns: 1fr; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_signal_card(titulo: str, probabilidad: float) -> None:
    es_value = probabilidad >= VALUE_BET_THRESHOLD
    clase = "signal-card value-bet" if es_value else "signal-card"
    st.markdown(
        f"""
        <div class="{clase}">
            <div class="signal-label">{titulo}</div>
            <div class="signal-value">{probabilidad * 100:.1f}%</div>
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
    def fmt_num(valor: float, disponible: bool = True, porcentaje: bool = False) -> str:
        if not disponible:
            return "-"
        if porcentaje:
            return f"{valor * 100:.1f}%"
        return f"{valor:.2f}"

    st.markdown(
        f"""
        <div class="split-card">
            <h4>{titulo}</h4>
            <div class="split-grid">
                <div class="mini-stat"><strong>{stats['pj']}</strong><span>Partidos</span></div>
                <div class="mini-stat"><strong>{stats['gf']:.2f}</strong><span>Goles a favor</span></div>
                <div class="mini-stat"><strong>{stats['gc']:.2f}</strong><span>Goles en contra</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['corners_for'], stats.get('has_corners', False))}</strong><span>Corners for</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['corners_against'], stats.get('has_corners', False))}</strong><span>Corners against</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['shots_for'], stats.get('has_shots', False))}</strong><span>Remates</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['shots_against'], stats.get('has_shots', False))}</strong><span>Remates rivales</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['shots_on_target_for'], stats.get('has_shots_on_target', False))}</strong><span>Remates a puerta</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['shots_on_target_against'], stats.get('has_shots_on_target', False))}</strong><span>A puerta rival</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['win_pct'], porcentaje=True)}</strong><span>Victorias</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['draw_pct'], porcentaje=True)}</strong><span>Empates</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['loss_pct'], porcentaje=True)}</strong><span>Derrotas</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['btts_pct'], porcentaje=True)}</strong><span>BTTS</span></div>
                <div class="mini-stat"><strong>{fmt_num(stats['over25_pct'], porcentaje=True)}</strong><span>Over 2.5</span></div>
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


def render_league_hub(league_rows: list[dict], fecha_objetivo, hoy) -> str | None:
    total_partidos = sum(item["match_count"] for item in league_rows)
    ligas_activas = sum(1 for item in league_rows if item["match_count"] > 0)

    st.markdown(
        f"""
        <div class="league-summary-grid">
            <div class="league-summary-card">
                <span>Partidos en la fecha</span>
                <strong>{total_partidos}</strong>
            </div>
            <div class="league-summary-card">
                <span>Ligas con actividad</span>
                <strong>{ligas_activas}</strong>
            </div>
            <div class="league-summary-card">
                <span>Competiciones visibles</span>
                <strong>{len(league_rows)}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for inicio in range(0, len(league_rows), 3):
        bloque = league_rows[inicio : inicio + 3]
        cols = st.columns(len(bloque))
        for indice, (col, item) in enumerate(zip(cols, bloque), start=inicio + 1):
            etiqueta = "Mas activa" if indice == 1 and item["match_count"] > 0 else f"Top {indice}"
            partido_label = "partidos" if item["match_count"] != 1 else "partido"
            with col:
                st.markdown(
                    f"""
                    <div class="league-card">
                        <div class="league-card-top">
                            <div>
                                <div class="league-card-country">{item['country']}</div>
                                <div class="league-card-title">{item['league']}</div>
                            </div>
                            <div class="league-rank-pill">{etiqueta}</div>
                        </div>
                        <div class="league-card-count">{item['match_count']}</div>
                        <div class="league-card-count-label">{partido_label} en la fecha</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Ver liga" if item["match_count"] > 0 else "Abrir liga",
                    key=f"league_hub_{safe_key(item['league'])}",
                    use_container_width=True,
                ):
                    return item["league"]
    return None


def render_comparador_cuotas(filas: list[dict]) -> None:
    if not filas:
        return

    filas_ordenadas = sorted(filas, key=lambda item: item["edge"], reverse=True)
    positivos = [fila for fila in filas_ordenadas if fila["edge"] > 0]
    mejor = filas_ordenadas[0]

    st.markdown(
        f"""
        <div class="odds-panel">
            <div class="odds-panel-head">
                <div>
                    <h3>Lectura rapida del mercado</h3>
                    <p>La tabla prioriza edge, break-even y diferencia real entre la cuota justa y la oferta de la casa.</p>
                </div>
            </div>
            <div class="odds-overview">
                <div class="odds-summary-card">
                    <span>Value bets detectadas</span>
                    <strong>{len(positivos)}</strong>
                </div>
                <div class="odds-summary-card">
                    <span>Mejor edge</span>
                    <strong>{mejor['edge'] * 100:+.2f}%</strong>
                </div>
                <div class="odds-summary-card">
                    <span>Mercado lider</span>
                    <strong>{mejor['market']}</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for fila in filas_ordenadas:
        if fila["edge"] > 0:
            clase = "value"
            lectura = "La cuota ofrecida esta por encima del break-even del modelo."
        elif fila["offered_odds"] >= fila["fair_odds"]:
            clase = "flat"
            lectura = "Mercado practicamente alineado con la cuota justa."
        else:
            clase = "bad"
            lectura = "La casa paga por debajo de la cuota justa del modelo."

        st.markdown(
            f"""
            <div class="odds-row {clase}">
                <div class="odds-row-top">
                    <div>
                        <div class="odds-market">{fila['market']}</div>
                        <div class="odds-note">{lectura}</div>
                    </div>
                    <div class="odds-badge {clase}">{fila['edge'] * 100:+.2f}%</div>
                </div>
                <div class="odds-metrics">
                    <div class="odds-metric"><span>Prob IA</span><strong>{fila['prob'] * 100:.1f}%</strong></div>
                    <div class="odds-metric"><span>Cuota justa</span><strong>@{fila['fair_odds']:.2f}</strong></div>
                    <div class="odds-metric"><span>Cuota casa</span><strong>@{fila['offered_odds']:.2f}</strong></div>
                    <div class="odds-metric"><span>Diferencia</span><strong>{fila['offered_odds'] - fila['fair_odds']:+.2f}</strong></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_player_props_panel(api_ready: bool) -> None:
    estado = "API lista para conectar" if api_ready else "Falta configurar token y mapping del fixture"
    st.markdown(
        f"""
        <div class="player-api-card">
            <h3>Integracion de jugadores</h3>
            <p>Fuente recomendada: Sportmonks Football API. Es la opcion que mejor encaja para remates, remates a puerta, faltas cometidas y faltas recibidas por jugador.</p>
            <p>{estado}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="player-prop-grid">
            <div class="player-prop-card">
                <h4>Remates a puerta por jugador</h4>
                <p>Base para proyectar lineas de tiros a puerta y detectar perfiles con volumen estable.</p>
                <span>Shots on target</span>
            </div>
            <div class="player-prop-card">
                <h4>Remates por jugador</h4>
                <p>Sirve para modelar volumen ofensivo total, no solo finalizacion precisa.</p>
                <span>Total shots</span>
            </div>
            <div class="player-prop-card">
                <h4>Faltas cometidas</h4>
                <p>Util para props defensivas, tarjetas y perfiles de riesgo por posicion o rol.</p>
                <span>Fouls committed</span>
            </div>
            <div class="player-prop-card">
                <h4>Faltas recibidas</h4>
                <p>Clave para detectar extremos, mediapuntas y delanteros que fuerzan contacto.</p>
                <span>Fouls drawn</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not api_ready:
        st.markdown(
            """
            <div class="empty-panel">
                <h3>Estado actual de la integracion</h3>
                <p>La pestaña ya esta preparada a nivel de producto, pero falta conectar un proveedor externo con token y resolver el enlace entre nuestro partido y el fixture del proveedor.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_fixture_cards(partidos: pd.DataFrame, fecha_objetivo, hoy) -> pd.Series | None:
    if partidos.empty:
        return None
    titulo_lista = "Partidos de hoy" if fecha_objetivo == hoy else f"Partidos del {fecha_objetivo.strftime('%d/%m/%Y')}"
    st.markdown(f'<div class="section-title">{titulo_lista}</div>', unsafe_allow_html=True)
    opciones_partidos = partidos["FixtureLabel"].tolist()
    if st.session_state.get("fixture_label") not in opciones_partidos:
        st.session_state["fixture_label"] = opciones_partidos[0]
    filas_partidos = partidos.to_dict("records")
    if len(filas_partidos) > 6:
        st.markdown(
            """
            <div class="fixture-table-head">
                <div>Hora</div>
                <div>Partido</div>
                <div>Panel</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for indice, partido in enumerate(filas_partidos):
            seleccion_actual = st.session_state.get("fixture_label") == partido["FixtureLabel"]
            clase = "fixture-table-block active" if seleccion_actual else "fixture-table-block"
            row_cols = st.columns([1.0, 2.4, 1.0], vertical_alignment="center")
            with row_cols[0]:
                st.markdown(
                    f"""
                    <div class="{clase}">
                        <div class="fixture-table-cell">{partido.get('MatchDate').strftime('%d/%m/%Y') if partido.get('MatchDate') else 'Sin fecha'} {partido.get('Time', '').strip()}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with row_cols[1]:
                st.markdown(
                    f"""
                    <div class="{clase}">
                        <div class="fixture-table-match">
                            <strong>{nombre_visual_equipo(partido.get('HomeTeam', 'TBD'))} vs {nombre_visual_equipo(partido.get('AwayTeam', 'TBD'))}</strong>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with row_cols[2]:
                if st.button(
                    "Abierto" if seleccion_actual else "Ver",
                    key=f"fixture_table_{safe_key(partido['FixtureLabel'])}_{indice}",
                    use_container_width=True,
                    disabled=seleccion_actual,
                ):
                    st.session_state["fixture_label"] = partido["FixtureLabel"]
                    st.rerun()
    else:
        for inicio in range(0, len(filas_partidos), 2):
            bloque = filas_partidos[inicio : inicio + 2]
            cols = st.columns(2)
            for col, partido in zip(cols, bloque):
                seleccion_actual = st.session_state.get("fixture_label") == partido["FixtureLabel"]
                clase = "fixture-card active" if seleccion_actual else "fixture-card"
                with col:
                    st.markdown(
                        f"""
                        <div class="{clase}">
                            <div class="fixture-meta">
                                <span>{partido.get('MatchDate').strftime('%d/%m/%Y') if partido.get('MatchDate') else 'Sin fecha'} {partido.get('Time', '').strip()}</span>
                            </div>
                            <div class="fixture-teams">{nombre_visual_equipo(partido.get('HomeTeam', 'TBD'))}<br>vs<br>{nombre_visual_equipo(partido.get('AwayTeam', 'TBD'))}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Abierto" if seleccion_actual else "Ver estadisticas",
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
                <div><div class="signal-label">Ultimos {form['matches']} partidos</div><h4>{team}</h4></div>
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
    if h2h["matches"] > 0:
        detalle = textwrap.dedent(
            f"""
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
            """
        ).strip()
    else:
        detalle = textwrap.dedent(
            """
            <div class="form-meta">
                <span>Sin enfrentamientos directos en la muestra</span>
                <span>Se usa el contexto reciente general de ambos equipos</span>
            </div>
            """
        ).strip()
    st.markdown(
        f"""
        <div class="form-card">
            <div class="form-head">
                <div><div class="signal-label">Resumen H2H</div><h4>{local} vs {visitante}</h4></div>
                <div class="form-ppg">{h2h['matches']}<span>Partidos</span></div>
            </div>
            {detalle}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_h2h_explorer(h2h: dict) -> None:
    partidos = h2h.get("recent_matches", [])
    if not partidos:
        return
    ids = [partido["id"] for partido in partidos]
    if st.session_state.get("selected_h2h_match") not in ids:
        st.session_state["selected_h2h_match"] = ids[0]
    st.markdown("### Ultimos enfrentamientos")
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
                        <div class="h2h-meta"><span>{partido['date']} | {partido['winner']}</span></div>
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


def _fmt_comparativa(valor: float, porcentaje: bool = False, sufijo: str = "") -> str:
    if porcentaje:
        return f"{valor * 100:.1f}%"
    return f"{valor:.2f}{sufijo}"


def _fmt_comparativa_condicional(valor: float, disponible: bool, porcentaje: bool = False) -> str:
    if not disponible:
        return "-"
    return _fmt_comparativa(valor, porcentaje=porcentaje)


def _leer_ventaja(local: str, visitante: str, valor_local: float, valor_visitante: float, invertido: bool = False, porcentaje: bool = False) -> str:
    diferencia_real = valor_local - valor_visitante
    diferencia_lectura = -diferencia_real if invertido else diferencia_real
    umbral = 0.02 if porcentaje else 0.05
    if abs(diferencia_lectura) < umbral:
        return "Muy parejo"

    ganador = local if diferencia_lectura > 0 else visitante
    magnitud = abs(diferencia_real) * (100 if porcentaje else 1)
    sufijo = " pp" if porcentaje else ""
    return f"Ventaja {ganador} ({magnitud:.1f}{sufijo})"


def _leer_ventaja_si_hay_datos(
    local: str,
    visitante: str,
    valor_local: float,
    valor_visitante: float,
    disponible_local: bool,
    disponible_visitante: bool,
    invertido: bool = False,
    porcentaje: bool = False,
) -> str:
    if not (disponible_local and disponible_visitante):
        return "Sin datos suficientes"
    return _leer_ventaja(local, visitante, valor_local, valor_visitante, invertido=invertido, porcentaje=porcentaje)


def tabla_comparativa(local: str, visitante: str, stats_local: dict, stats_visitante: dict, h2h: dict) -> pd.DataFrame:
    local_home = stats_local["home"]
    visitante_away = stats_visitante["away"]
    local_overall = stats_local["overall"]
    visitante_overall = stats_visitante["overall"]
    local_recent = stats_local["recent_overall"]
    visitante_recent = stats_visitante["recent_overall"]
    local_context = stats_local["comparison_form"]
    visitante_context = stats_visitante["comparison_form"]
    recent_window = stats_local.get("recent_window", 10)
    context_window = stats_local.get("comparison_window", 8)
    contexto_h2h = (
        f"{h2h['matches']} H2H + otros partidos recientes"
        if h2h["matches"] > 0
        else f"Sin H2H: fallback a ultimos {context_window} partidos generales"
    )

    filas = [
        {
            "Metric": "GF escenario casa/fuera",
            f"{local}": _fmt_comparativa(local_home["gf"]),
            f"{visitante}": _fmt_comparativa(visitante_away["gf"]),
            "Lectura": _leer_ventaja(local, visitante, local_home["gf"], visitante_away["gf"]),
        },
        {
            "Metric": "GC escenario casa/fuera",
            f"{local}": _fmt_comparativa(local_home["gc"]),
            f"{visitante}": _fmt_comparativa(visitante_away["gc"]),
            "Lectura": _leer_ventaja(local, visitante, local_home["gc"], visitante_away["gc"], invertido=True),
        },
        {
            "Metric": "Corners escenario casa/fuera",
            f"{local}": _fmt_comparativa_condicional(local_home["corners_for"], local_home.get("has_corners", False)),
            f"{visitante}": _fmt_comparativa_condicional(visitante_away["corners_for"], visitante_away.get("has_corners", False)),
            "Lectura": _leer_ventaja_si_hay_datos(
                local,
                visitante,
                local_home["corners_for"],
                visitante_away["corners_for"],
                local_home.get("has_corners", False),
                visitante_away.get("has_corners", False),
            ),
        },
        {
            "Metric": "Remates escenario casa/fuera",
            f"{local}": _fmt_comparativa_condicional(local_home["shots_for"], local_home.get("has_shots", False)),
            f"{visitante}": _fmt_comparativa_condicional(visitante_away["shots_for"], visitante_away.get("has_shots", False)),
            "Lectura": _leer_ventaja_si_hay_datos(
                local,
                visitante,
                local_home["shots_for"],
                visitante_away["shots_for"],
                local_home.get("has_shots", False),
                visitante_away.get("has_shots", False),
            ),
        },
        {
            "Metric": "Remates a puerta escenario",
            f"{local}": _fmt_comparativa_condicional(local_home["shots_on_target_for"], local_home.get("has_shots_on_target", False)),
            f"{visitante}": _fmt_comparativa_condicional(visitante_away["shots_on_target_for"], visitante_away.get("has_shots_on_target", False)),
            "Lectura": _leer_ventaja_si_hay_datos(
                local,
                visitante,
                local_home["shots_on_target_for"],
                visitante_away["shots_on_target_for"],
                local_home.get("has_shots_on_target", False),
                visitante_away.get("has_shots_on_target", False),
            ),
        },
        {
            "Metric": "GF global temporada",
            f"{local}": _fmt_comparativa(local_overall["gf"]),
            f"{visitante}": _fmt_comparativa(visitante_overall["gf"]),
            "Lectura": _leer_ventaja(local, visitante, local_overall["gf"], visitante_overall["gf"]),
        },
        {
            "Metric": "GC global temporada",
            f"{local}": _fmt_comparativa(local_overall["gc"]),
            f"{visitante}": _fmt_comparativa(visitante_overall["gc"]),
            "Lectura": _leer_ventaja(local, visitante, local_overall["gc"], visitante_overall["gc"], invertido=True),
        },
        {
            "Metric": f"GF ultimos {recent_window} generales",
            f"{local}": _fmt_comparativa(local_recent["gf"]),
            f"{visitante}": _fmt_comparativa(visitante_recent["gf"]),
            "Lectura": _leer_ventaja(local, visitante, local_recent["gf"], visitante_recent["gf"]),
        },
        {
            "Metric": f"GC ultimos {recent_window} generales",
            f"{local}": _fmt_comparativa(local_recent["gc"]),
            f"{visitante}": _fmt_comparativa(visitante_recent["gc"]),
            "Lectura": _leer_ventaja(local, visitante, local_recent["gc"], visitante_recent["gc"], invertido=True),
        },
        {
            "Metric": f"Corners ultimos {recent_window}",
            f"{local}": _fmt_comparativa_condicional(local_recent["corners_for"], local_recent.get("has_corners", False)),
            f"{visitante}": _fmt_comparativa_condicional(visitante_recent["corners_for"], visitante_recent.get("has_corners", False)),
            "Lectura": _leer_ventaja_si_hay_datos(
                local,
                visitante,
                local_recent["corners_for"],
                visitante_recent["corners_for"],
                local_recent.get("has_corners", False),
                visitante_recent.get("has_corners", False),
            ),
        },
        {
            "Metric": f"Remates ultimos {recent_window}",
            f"{local}": _fmt_comparativa_condicional(local_recent["shots_for"], local_recent.get("has_shots", False)),
            f"{visitante}": _fmt_comparativa_condicional(visitante_recent["shots_for"], visitante_recent.get("has_shots", False)),
            "Lectura": _leer_ventaja_si_hay_datos(
                local,
                visitante,
                local_recent["shots_for"],
                visitante_recent["shots_for"],
                local_recent.get("has_shots", False),
                visitante_recent.get("has_shots", False),
            ),
        },
        {
            "Metric": f"Remates a puerta ultimos {recent_window}",
            f"{local}": _fmt_comparativa_condicional(local_recent["shots_on_target_for"], local_recent.get("has_shots_on_target", False)),
            f"{visitante}": _fmt_comparativa_condicional(visitante_recent["shots_on_target_for"], visitante_recent.get("has_shots_on_target", False)),
            "Lectura": _leer_ventaja_si_hay_datos(
                local,
                visitante,
                local_recent["shots_on_target_for"],
                visitante_recent["shots_on_target_for"],
                local_recent.get("has_shots_on_target", False),
                visitante_recent.get("has_shots_on_target", False),
            ),
        },
        {
            "Metric": f"BTTS ultimos {recent_window}",
            f"{local}": _fmt_comparativa(local_recent["btts_pct"], porcentaje=True),
            f"{visitante}": _fmt_comparativa(visitante_recent["btts_pct"], porcentaje=True),
            "Lectura": _leer_ventaja(local, visitante, local_recent["btts_pct"], visitante_recent["btts_pct"], porcentaje=True),
        },
        {
            "Metric": f"Over 2.5 ultimos {recent_window}",
            f"{local}": _fmt_comparativa(local_recent["over25_pct"], porcentaje=True),
            f"{visitante}": _fmt_comparativa(visitante_recent["over25_pct"], porcentaje=True),
            "Lectura": _leer_ventaja(local, visitante, local_recent["over25_pct"], visitante_recent["over25_pct"], porcentaje=True),
        },
        {
            "Metric": f"Forma ultimos {recent_window}",
            f"{local}": f"{stats_local['form']['streak']} ({stats_local['form']['ppg']:.2f} ppg)",
            f"{visitante}": f"{stats_visitante['form']['streak']} ({stats_visitante['form']['ppg']:.2f} ppg)",
            "Lectura": _leer_ventaja(local, visitante, stats_local["form"]["ppg"], stats_visitante["form"]["ppg"]),
        },
        {
            "Metric": f"Contexto extra ultimos {context_window}",
            f"{local}": f"{local_context['streak']} ({local_context['ppg']:.2f} ppg)",
            f"{visitante}": f"{visitante_context['streak']} ({visitante_context['ppg']:.2f} ppg)",
            "Lectura": contexto_h2h,
        },
    ]
    return pd.DataFrame(filas)


def render_traceability_panel(analisis: dict) -> None:
    trace = analisis["trace"]
    st.markdown('<div class="trace-card"><h3>Trazabilidad del modelo</h3></div>', unsafe_allow_html=True)
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
            ("Ajuste H2H/contexto", f"{datos['h2h_adjustment']:+.3f}"),
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
        return
    top_items = ranking[:3]
    rest_items = ranking[3:8]
    badge_label = f"{len(ranking)} picks" if len(ranking) != 1 else "1 pick"

    st.markdown(
        f"""
        <div class="ranking-card">
            <div class="ranking-head">
                <div class="ranking-head-copy">
                    <h3>Top edges de {fecha_label}</h3>
                </div>
                <div class="ranking-badge">{badge_label}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if top_items:
        top_cols = st.columns(len(top_items))
        for idx, (col, fila) in enumerate(zip(top_cols, top_items), start=1):
            edge_pct = fila["edge"] * 100
            edge_class = "negative" if edge_pct < 0 else ""
            extra_class = " top-1" if idx == 1 else ""
            with col:
                st.markdown(
                    f"""
                    <div class="ranking-spotlight{extra_class}">
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
                    """,
                    unsafe_allow_html=True,
                )

    if rest_items:
        st.markdown(
            """
            <div class="ranking-subtable">
                <div class="ranking-subhead">
                    <div>Partido y mercado</div>
                    <div>Edge</div>
                    <div>Casa</div>
                    <div>Justa</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for fila in rest_items:
            edge_pct = fila["edge"] * 100
            edge_class = "edge-pos" if edge_pct >= 0 else "edge-neg"
            row_cols = st.columns([2.8, 1, 1, 1], vertical_alignment="center")
            with row_cols[0]:
                st.markdown(
                    f"""
                    <div class="ranking-row-card ranking-cell-main">
                        <strong>{fila['match']}</strong>
                        <span>{fila['market']}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with row_cols[1]:
                st.markdown(
                    f'<div class="ranking-row-card"><span class="ranking-pill {edge_class}">{edge_pct:+.2f}%</span></div>',
                    unsafe_allow_html=True,
                )
            with row_cols[2]:
                st.markdown(
                    f'<div class="ranking-row-card"><span class="ranking-pill">@{fila["offered_odds"]:.2f}</span></div>',
                    unsafe_allow_html=True,
                )
            with row_cols[3]:
                st.markdown(
                    f'<div class="ranking-row-card"><span class="ranking-pill">@{fila["fair_odds"]:.2f}</span></div>',
                    unsafe_allow_html=True,
                )
