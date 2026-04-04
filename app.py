from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
import streamlit as st

from core.model import (
    SIMULACIONES,
    construir_insights,
    construir_ranking_value_bets,
    cuota_justa,
    guardar_analisis,
    stake_kelly,
)
from data.sources import (
    ESPN_LEAGUE_IDS,
    LEAGUE_CONFIGS,
    LOCAL_TIMEZONE,
    construir_cuotas_automaticas,
    descargar_datos_liga,
    descargar_fixture_espn,
    descargar_resumen_espn,
    extraer_contexto_mercado_espn,
    fusionar_calendarios,
    preparar_calendario,
)
from storage.favorites import (
    agregar_favorito,
    cargar_favoritos,
    eliminar_favorito,
    vaciar_favoritos,
)
from ui.components import (
    inyectar_estilos,
    render_comparador_cuotas,
    render_expected_card,
    render_fixture_cards,
    render_form_card,
    render_h2h_explorer,
    render_h2h_summary_card,
    render_insight_panel,
    render_radar_panel,
    render_ranking_value_panel,
    render_signal_card,
    render_split_panel,
    render_summary_band,
    safe_key,
    tabla_comparativa,
)


st.set_page_config(page_title="Gordon BetScanner", layout="wide")


@st.cache_data(ttl=300, show_spinner=False)
def construir_ranking_liga(df: pd.DataFrame, liga: str, league_id: str, partidos_serializados: list[dict]) -> list[dict]:
    items = []
    for partido in partidos_serializados:
        if not partido.get("EventId"):
            continue
        analisis = guardar_analisis(
            df,
            liga,
            partido["HomeTeam"],
            partido["AwayTeam"],
            match_date=partido.get("MatchDate"),
            match_label=partido.get("FixtureLabel", ""),
        )
        if analisis is None:
            continue
        resumen = descargar_resumen_espn(league_id, str(partido["EventId"]))
        contexto = extraer_contexto_mercado_espn(resumen) if resumen else {}
        auto_odds = construir_cuotas_automaticas(contexto, analisis["local"], analisis["visitante"])
        items.append({"analysis": analisis, "auto_odds": auto_odds})
    return construir_ranking_value_bets(items, limite=10)


inyectar_estilos()

for key, default in {
    "analysis": None,
    "analysis_signature": None,
    "solo_hoy_toggle": True,
    "last_league": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.markdown(
    """
    <div class="titlebar">
        <div class="titlebar-copy">
            <h1>Gordon BetScanner</h1>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

top_1, top_2, top_3, top_4 = st.columns([1.25, 0.9, 1.05, 0.6])
with top_1:
    liga_seleccionada = st.selectbox("Liga", list(LEAGUE_CONFIGS.keys()))

if st.session_state.get("last_league") != liga_seleccionada:
    st.session_state["solo_hoy_toggle"] = True
    st.session_state["fixture_label"] = None
    st.session_state["last_league"] = liga_seleccionada

df = descargar_datos_liga(liga_seleccionada) if liga_seleccionada else None
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
if not partidos_filtrados.empty and "EventId" not in partidos_filtrados.columns:
    partidos_filtrados["EventId"] = ""

with top_4:
    st.metric("Partidos", len(partidos_filtrados))
st.markdown('<div class="layout-divider"></div>', unsafe_allow_html=True)

layout_left, layout_right = st.columns([0.92, 1.58], gap="large")

with layout_left:
    partido_seleccionado = render_fixture_cards(partidos_filtrados, fecha_objetivo, hoy) if not partidos_filtrados.empty else None

local = partido_seleccionado["HomeTeam"] if partido_seleccionado is not None else None
visitante = partido_seleccionado["AwayTeam"] if partido_seleccionado is not None else None

ranking = []
if df is not None and not partidos_filtrados.empty and league_id:
    ranking = construir_ranking_liga(
        df,
        liga_seleccionada,
        league_id,
        partidos_filtrados[["HomeTeam", "AwayTeam", "MatchDate", "FixtureLabel", "EventId"]].fillna("").to_dict("records"),
    )

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
        with st.spinner("Cargando..."):
            st.session_state["analysis"] = guardar_analisis(
                df,
                liga_seleccionada,
                local,
                visitante,
                match_date=partido_seleccionado["MatchDate"],
                match_label=partido_seleccionado["FixtureLabel"],
            )
        st.session_state["analysis_signature"] = firma_actual
analisis = st.session_state.get("analysis")
resumen_espn = {}
if partido_seleccionado is not None and league_id and partido_seleccionado.get("EventId"):
    resumen_espn = descargar_resumen_espn(league_id, str(partido_seleccionado["EventId"]))

with layout_left:
    if ranking:
        render_ranking_value_panel(ranking, fecha_objetivo.strftime("%d/%m/%Y"))

with layout_right:
    if analisis is not None:
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
            render_radar_panel(analisis)

        tab_stats, tab_compare, tab_match, tab_odds = st.tabs(
            ["Estadisticas generales", "Comparativa equipos", "Posibles estadisticas del partido", "Comparador cuota real vs cuota justa"]
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
            st.dataframe(
                tabla_comparativa(
                    analisis["local"],
                    analisis["visitante"],
                    analisis["stats_local"]["home"],
                    analisis["stats_visitante"]["away"],
                    analisis["stats_local"]["overall"],
                    analisis["stats_visitante"]["overall"],
                ),
                use_container_width=True,
                hide_index=True,
            )
            insight_left, insight_right = st.columns([1.3, 1])
            with insight_left:
                render_insight_panel(construir_insights(analisis))
            with insight_right:
                render_h2h_summary_card(analisis["h2h"], analisis["local"], analisis["visitante"])
            st.markdown("### Forma reciente")
            form_left, form_right = st.columns(2)
            with form_left:
                render_form_card(analisis["local"], analisis["stats_local"]["form"])
            with form_right:
                render_form_card(analisis["visitante"], analisis["stats_visitante"]["form"])
            render_h2h_explorer(analisis["h2h"])

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
            contexto_mercado = extraer_contexto_mercado_espn(resumen_espn) if resumen_espn else {}
            auto_odds = construir_cuotas_automaticas(contexto_mercado, analisis["local"], analisis["visitante"])

            odds_cols = st.columns(3)
            cuotas_usuario: dict[str, float] = {}
            match_key = safe_key(f"{analisis['local']}_{analisis['visitante']}_{analisis['match_date']}")
            for indice, mercado in enumerate(mercados):
                clave = safe_key(mercado["nombre"])
                cuota_default = auto_odds.get(mercado["nombre"], {}).get("odds", max(1.05, round(cuota_justa(mercado["prob"]), 2)))
                etiqueta = mercado["nombre"]
                if mercado["nombre"] in auto_odds:
                    etiqueta = f"{mercado['nombre']} ({auto_odds[mercado['nombre']]['provider']})"
                with odds_cols[indice % 3]:
                    cuotas_usuario[mercado["nombre"]] = st.number_input(
                        f"Cuota {etiqueta}",
                        min_value=1.01,
                        value=float(cuota_default),
                        step=0.01,
                        key=f"odd_{match_key}_{clave}",
                    )

            filas_comparador = []
            for mercado in mercados:
                cuota_real = cuotas_usuario[mercado["nombre"]]
                cuota_fair = cuota_justa(mercado["prob"])
                edge = (mercado["prob"] * cuota_real) - 1
                filas_comparador.append({"market": mercado["nombre"], "prob": mercado["prob"], "fair_odds": cuota_fair, "offered_odds": cuota_real, "edge": edge})
            render_comparador_cuotas(filas_comparador)

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
                cuota_input = st.number_input("Cuota usada en Kelly", min_value=1.01, value=float(cuota_seleccionada), step=0.01, key=f"kelly_custom_odd_{match_key}_{safe_key(mercado_kelly)}")

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
                st.rerun()
            if limpiar_picks:
                vaciar_favoritos()
                st.rerun()

            favoritos = cargar_favoritos()
            if favoritos:
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
