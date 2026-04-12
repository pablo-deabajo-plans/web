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
from data.teams import nombre_visual_equipo
from ui.components import (
    inyectar_estilos,
    render_comparador_cuotas,
    render_expected_card,
    render_fixture_cards,
    render_form_card,
    render_h2h_explorer,
    render_h2h_summary_card,
    render_insight_panel,
    render_league_hub,
    render_radar_panel,
    render_ranking_value_panel,
    render_signal_card,
    render_split_panel,
    render_summary_band,
    safe_key,
    tabla_comparativa,
)


st.set_page_config(page_title="Gordon BetScanner", layout="wide")


LEAGUE_COUNTRIES = {
    "Premier League": "Inglaterra",
    "LaLiga": "Espana",
    "Segunda Division": "Espana",
    "Serie A": "Italia",
    "Bundesliga": "Alemania",
    "Ligue 1": "Francia",
    "Holanda": "Paises Bajos",
    "Liga de Portugal": "Portugal",
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
    "WSL Femenina": "Inglaterra",
    "Liga F": "Espana",
    "Premiere Ligue Femenina": "Francia",
    "Frauen-Bundesliga": "Alemania",
    "Serie A Femenina": "Italia",
}


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


@st.cache_data(ttl=300, show_spinner=False)
def resumir_liga_para_portada(liga: str, fecha_objetivo, hoy) -> dict:
    config = LEAGUE_CONFIGS.get(liga, {})
    history = config.get("history", {})
    source_type = history.get("type", "")
    league_id = ESPN_LEAGUE_IDS.get(liga, "")

    df = descargar_datos_liga(liga) if source_type in {"football_data", "footystats_fixtures"} else None
    calendario_csv = preparar_calendario(df) if df is not None else pd.DataFrame()
    equipos_csv = sorted(df["HomeTeam"].dropna().unique()) if df is not None and "HomeTeam" in df.columns else []
    partidos_csv = calendario_csv[calendario_csv["MatchDate"] == fecha_objetivo].copy() if not calendario_csv.empty else pd.DataFrame()

    partidos_espn = pd.DataFrame()
    if league_id and (source_type == "espn_scoreboard" or fecha_objetivo >= hoy or partidos_csv.empty):
        partidos_espn = descargar_fixture_espn(league_id, fecha_objetivo)

    base_csv = partidos_csv if source_type != "espn_scoreboard" else pd.DataFrame()
    partidos = fusionar_calendarios(base_csv, partidos_espn, equipos_csv)
    return {
        "league": liga,
        "country": LEAGUE_COUNTRIES.get(liga, "Internacional"),
        "match_count": len(partidos),
    }


@st.cache_data(ttl=300, show_spinner=False)
def construir_portada_ligas(fecha_objetivo, hoy) -> list[dict]:
    filas = [resumir_liga_para_portada(liga, fecha_objetivo, hoy) for liga in LEAGUE_CONFIGS]
    return sorted(filas, key=lambda item: (-item["match_count"], item["league"]))


@st.cache_data(ttl=300, show_spinner=False)
def buscar_partidos_global(fecha_objetivo, hoy, query: str) -> list[dict]:
    termino = query.strip().lower()
    if not termino:
        return []

    resultados = []
    for liga in LEAGUE_CONFIGS:
        config = LEAGUE_CONFIGS.get(liga, {})
        history = config.get("history", {})
        source_type = history.get("type", "")
        league_id = ESPN_LEAGUE_IDS.get(liga, "")

        df = descargar_datos_liga(liga) if source_type in {"football_data", "footystats_fixtures"} else None
        calendario_csv = preparar_calendario(df) if df is not None else pd.DataFrame()
        equipos_csv = sorted(df["HomeTeam"].dropna().unique()) if df is not None and "HomeTeam" in df.columns else []
        partidos_csv = calendario_csv[calendario_csv["MatchDate"] == fecha_objetivo].copy() if not calendario_csv.empty else pd.DataFrame()

        partidos_espn = pd.DataFrame()
        if league_id and (source_type == "espn_scoreboard" or fecha_objetivo >= hoy or partidos_csv.empty):
            partidos_espn = descargar_fixture_espn(league_id, fecha_objetivo)

        base_csv = partidos_csv if source_type != "espn_scoreboard" else pd.DataFrame()
        partidos = fusionar_calendarios(base_csv, partidos_espn, equipos_csv)
        if partidos.empty:
            continue

        if "EventId" not in partidos.columns:
            partidos["EventId"] = ""

        for partido in partidos.to_dict("records"):
            local = nombre_visual_equipo(partido.get("HomeTeam", "TBD"))
            visitante = nombre_visual_equipo(partido.get("AwayTeam", "TBD"))
            match_text = f"{local} vs {visitante}".lower()
            if termino not in match_text and termino not in local.lower() and termino not in visitante.lower():
                continue
            resultados.append(
                {
                    "league": liga,
                    "country": LEAGUE_COUNTRIES.get(liga, "Internacional"),
                    "match": f"{local} vs {visitante}",
                    "time": str(partido.get("Time", "")).strip(),
                    "fixture_label": partido.get("FixtureLabel", ""),
                    "event_id": partido.get("EventId", ""),
                }
            )
    return resultados


def limpiar_contexto_partido() -> None:
    for key in ["fixture_label", "analysis", "analysis_signature", "selected_h2h_match"]:
        st.session_state[key] = None


inyectar_estilos()

for key, default in {
    "analysis": None,
    "analysis_signature": None,
    "solo_hoy_toggle": True,
    "selected_league": None,
    "match_search": "",
    "search_results": [],
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

hoy = datetime.now(LOCAL_TIMEZONE).date()
liga_activa = st.session_state.get("selected_league")
filtros_toggle, filtros_fecha, filtros_busqueda, filtros_lupa = st.columns([0.8, 1.05, 1.3, 0.18])
with filtros_toggle:
    solo_hoy = st.toggle("Partidos de hoy", key="solo_hoy_toggle")
with filtros_fecha:
    fecha_partido = st.date_input("Fecha", value=hoy, disabled=solo_hoy)
with filtros_busqueda:
    busqueda_partido = st.text_input("Buscar partido", key="match_search", placeholder="Equipo o partido")
with filtros_lupa:
    st.markdown('<div class="search-icon-spacer"></div>', unsafe_allow_html=True)
    buscar_click = st.button("\U0001F50D", key="match_search_button", use_container_width=True)

fecha_objetivo = hoy if solo_hoy else fecha_partido
if buscar_click:
    st.session_state["search_results"] = buscar_partidos_global(fecha_objetivo, hoy, busqueda_partido)

resultados_busqueda = st.session_state.get("search_results", [])
if busqueda_partido.strip():
    resultados_busqueda = buscar_partidos_global(fecha_objetivo, hoy, busqueda_partido)
    st.session_state["search_results"] = resultados_busqueda
else:
    resultados_busqueda = []
    st.session_state["search_results"] = []

if resultados_busqueda:
    st.markdown('<div class="search-results-shell">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">Resultados de busqueda</div>', unsafe_allow_html=True)
    for resultado in resultados_busqueda[:8]:
        cols = st.columns([3.1, 1.2, 0.9])
        with cols[0]:
            hora_label = resultado["time"] if resultado["time"] else "Sin hora"
            st.markdown(
                f"""
                <div class="search-result-card">
                    <strong>{resultado['match']}</strong>
                    <span>{resultado['league']} | {resultado['country']} | {hora_label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                f"""
                <div class="search-result-card search-result-meta">
                    <strong>{resultado['league']}</strong>
                    <span>{resultado['country']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cols[2]:
            if st.button("Abrir", key=f"search_open_{safe_key(resultado['league'])}_{safe_key(resultado['fixture_label'])}", use_container_width=True):
                st.session_state["selected_league"] = resultado["league"]
                st.session_state["fixture_label"] = resultado["fixture_label"]
                st.session_state["search_results"] = []
                st.session_state["analysis"] = None
                st.session_state["analysis_signature"] = None
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
elif busqueda_partido.strip():
    st.markdown(
        """
        <div class="empty-panel">
            <h3>No he encontrado partidos con esa busqueda</h3>
            <p>Prueba con el nombre de un equipo o una parte del cruce en la fecha seleccionada.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

if not liga_activa:
    with st.spinner("Cargando panorama de ligas..."):
        portada_ligas = construir_portada_ligas(fecha_objetivo, hoy)
    liga_elegida = render_league_hub(portada_ligas, fecha_objetivo, hoy)
    if liga_elegida:
        st.session_state["selected_league"] = liga_elegida
        limpiar_contexto_partido()
        st.rerun()
    st.stop()

liga_seleccionada = st.session_state.get("selected_league")
st.markdown(
    f"""
    <div class="toolbar-shell">
        <div class="toolbar-kicker">Liga activa</div>
        <div class="toolbar-title">{liga_seleccionada}</div>
        <div class="toolbar-meta">{LEAGUE_COUNTRIES.get(liga_seleccionada, "Internacional")} | Analisis disponible para {fecha_objetivo.strftime("%d/%m/%Y")}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

top_1, top_2, top_3 = st.columns([1.1, 0.7, 0.7])
with top_1:
    if st.button("Ver todas las ligas", use_container_width=True):
        st.session_state["selected_league"] = None
        limpiar_contexto_partido()
        st.rerun()

df = descargar_datos_liga(liga_seleccionada) if liga_seleccionada else None
calendario_csv = preparar_calendario(df) if df is not None else pd.DataFrame()
equipos_csv = sorted(df["HomeTeam"].dropna().unique()) if df is not None and "HomeTeam" in df.columns else []
league_id = ESPN_LEAGUE_IDS.get(liga_seleccionada, "")

partidos_csv = calendario_csv[calendario_csv["MatchDate"] == fecha_objetivo].copy() if not calendario_csv.empty else pd.DataFrame()
usar_fallback_espn = fecha_objetivo >= hoy or partidos_csv.empty
partidos_espn = descargar_fixture_espn(league_id, fecha_objetivo) if usar_fallback_espn and league_id else pd.DataFrame()
partidos_filtrados = fusionar_calendarios(partidos_csv, partidos_espn, equipos_csv)
if not partidos_filtrados.empty and "EventId" not in partidos_filtrados.columns:
    partidos_filtrados["EventId"] = ""

with top_2:
    st.metric("Partidos", len(partidos_filtrados))
with top_3:
    st.metric("Pais", LEAGUE_COUNTRIES.get(liga_seleccionada, "Internacional"))
st.markdown('<div class="layout-divider"></div>', unsafe_allow_html=True)

layout_left, layout_right = st.columns([0.92, 1.58], gap="large")

with layout_left:
    if not partidos_filtrados.empty:
        partido_seleccionado = render_fixture_cards(partidos_filtrados, fecha_objetivo, hoy)
    else:
        partido_seleccionado = None
        st.markdown(
            """
            <div class="empty-panel">
                <h3>No hay partidos cargados para esta liga en la fecha elegida</h3>
                <p>Cambia la fecha o vuelve al explorador de ligas para entrar por otra competicion con mas actividad.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
            st.markdown('<div class="section-title">Escenario + forma reciente + H2H</div>', unsafe_allow_html=True)
            st.dataframe(
                tabla_comparativa(
                    analisis["local"],
                    analisis["visitante"],
                    analisis["stats_local"],
                    analisis["stats_visitante"],
                    analisis["h2h"],
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
            cp_a, cp_b, cp_c, cp_d = st.columns(4)
            cp_a.metric(f"{analisis['local']} 4+ corners", f"{resultado['Home_Over35_Corn'] * 100:.1f}%")
            cp_b.metric(f"{analisis['local']} 5+ corners", f"{resultado['Home_Over45_Corn'] * 100:.1f}%")
            cp_c.metric(f"{analisis['visitante']} 4+ corners", f"{resultado['Away_Over35_Corn'] * 100:.1f}%")
            cp_d.metric(f"{analisis['visitante']} 5+ corners", f"{resultado['Away_Over45_Corn'] * 100:.1f}%")
            r_a, r_b, r_c, r_d = st.columns(4)
            r_a.metric(f"Remates {analisis['local']}", f"{resultado['Shots_Home']:.2f}")
            r_b.metric(f"Remates {analisis['visitante']}", f"{resultado['Shots_Away']:.2f}")
            r_c.metric(f"A puerta {analisis['local']}", f"{resultado['ShotsOnTarget_Home']:.2f}")
            r_d.metric(f"A puerta {analisis['visitante']}", f"{resultado['ShotsOnTarget_Away']:.2f}")
            t_a, t_b, t_c = st.columns(3)
            t_a.metric(f"Tarjetas {analisis['local']}", f"{resultado['Cards_Home']:.2f}")
            t_b.metric("Tarjetas totales", f"{resultado['Total_Cards']:.2f}")
            t_c.metric(f"Tarjetas {analisis['visitante']}", f"{resultado['Cards_Away']:.2f}")
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
    else:
        st.markdown(
            """
            <div class="empty-panel">
                <h3>Selecciona un partido para abrir el analisis</h3>
                <p>El detalle se cargara aqui con radar, comparativas, proyecciones y comparador de cuotas en cuanto abras un cruce.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
