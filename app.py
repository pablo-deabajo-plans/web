from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from ui.api_client import (
    BackendApiError,
    calculate_kelly,
    clear_favorites,
    compare_odds,
    create_favorite,
    delete_favorite,
    get_daily_value_ranking,
    get_favorites,
    get_league_dashboard,
    get_leagues,
    get_match_dashboard,
    search_matches,
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
    render_league_hub,
    render_player_props_panel,
    render_radar_panel,
    render_ranking_value_panel,
    render_match_executive_summary,
    render_signal_card,
    render_split_panel,
    render_summary_band,
    render_traceability_panel,
    safe_key,
)


st.set_page_config(page_title="Gordon BetScanner", layout="wide")
inyectar_estilos()


APP_TIMEZONE = ZoneInfo("Europe/Madrid")


def build_match_confidence_label(analisis: dict, odds_rows: list[dict]) -> tuple[str, str]:
    resultado = analisis["resultado"]
    probs = sorted([float(resultado["1"]), float(resultado["X"]), float(resultado["2"])], reverse=True)
    lead_margin = probs[0] - probs[1]
    best_edge = max((float(fila["edge"]) for fila in odds_rows), default=0.0)

    if lead_margin >= 0.12 and best_edge >= 0.04:
        return "Alta", "sesgo 1X2 claro y edge utilizable"
    if lead_margin >= 0.06 and best_edge > 0:
        return "Media", "hay sesgo de partido y precio por encima de la justa"
    if lead_margin >= 0.06:
        return "Media-baja", "hay lectura de partido, pero sin ventaja clara de precio"
    if best_edge > 0.04:
        return "Media", "el valor viene mas del precio que del sesgo base del partido"
    return "Baja", "partido abierto o mercado sin ventaja clara"


def render_match_decision_snapshot(analisis: dict, odds_rows: list[dict]) -> None:
    resultado = analisis["resultado"]
    local = analisis["local"]
    visitante = analisis["visitante"]
    probs = {
        local: float(resultado["1"]),
        "Empate": float(resultado["X"]),
        visitante: float(resultado["2"]),
    }
    ordered_probs = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    lead_name, lead_prob = ordered_probs[0]
    second_prob = ordered_probs[1][1]
    confidence_label, confidence_reason = build_match_confidence_label(analisis, odds_rows)
    positive_edges = sorted((fila for fila in odds_rows if float(fila["edge"]) > 0), key=lambda item: item["edge"], reverse=True)

    markets_text = "<p>Sin value claro en precios actuales.</p>"
    if positive_edges:
        markets_text = "".join(
            f"<p><strong>{fila['market']}</strong> | edge {float(fila['edge']) * 100:+.2f}% | cuota justa @{float(fila['fair_odds']):.2f} vs casa @{float(fila['offered_odds']):.2f}</p>"
            for fila in positive_edges[:3]
        )

    st.markdown(
        f"""
        <div class="panel">
            <div class="signal-label">Decision en 30-60 segundos</div>
            <p><strong>Ventaja base:</strong> {lead_name} lidera el 1X2 con {lead_prob * 100:.1f}% y deja al segundo escenario en {second_prob * 100:.1f}%.</p>
            <p><strong>Mercados accionables:</strong></p>
            {markets_text}
            <p><strong>Confianza:</strong> {confidence_label}. Motivo: {confidence_reason}.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def limpiar_contexto_partido() -> None:
    for key in ["fixture_label", "selected_h2h_match", "match_dashboard", "selected_match_context"]:
        st.session_state[key] = None


def ir_a_detalle_partido(*, league: str, match_id: str, fixture_label: str, target_date: date) -> None:
    st.session_state["selected_league"] = league
    st.session_state["fixture_label"] = fixture_label
    st.session_state["selected_h2h_match"] = None
    st.session_state["match_dashboard"] = None
    st.session_state["selected_match_context"] = {
        "league": league,
        "match_id": str(match_id),
        "target_date": target_date.isoformat(),
    }
    st.session_state["current_view"] = "match_detail"


def volver_a_liga() -> None:
    st.session_state["selected_h2h_match"] = None
    st.session_state["match_dashboard"] = None
    st.session_state["current_view"] = "league"


def volver_a_ligas() -> None:
    st.session_state["selected_league"] = None
    st.session_state["current_view"] = "league"
    limpiar_contexto_partido()


def ir_a_ranking_diario() -> None:
    st.session_state["current_view"] = "daily_value"
    st.session_state["selected_league"] = None
    limpiar_contexto_partido()


def render_search_results(resultados_busqueda: list[dict], fecha_objetivo: date) -> None:
    if resultados_busqueda:
        st.subheader("Resultados de busqueda")
        for resultado in resultados_busqueda[:8]:
            cols = st.columns([3.1, 1.2, 0.9])
            with cols[0]:
                hora_label = resultado["time"] if resultado["time"] else "Sin hora"
                st.write(resultado["match"])
                st.caption(f"{resultado['league']} | {resultado['country']} | {hora_label}")
            with cols[1]:
                st.write(resultado["league"])
                st.caption(resultado["country"])
            with cols[2]:
                if st.button(
                    "Abrir",
                    key=f"search_open_{safe_key(resultado['league'])}_{safe_key(resultado['fixture_label'])}",
                    use_container_width=True,
                ):
                    ir_a_detalle_partido(
                        league=resultado["league"],
                        match_id=resultado["match_id"],
                        fixture_label=resultado["fixture_label"],
                        target_date=fecha_objetivo,
                    )
                    st.session_state["search_results"] = []
                    st.session_state["search_executed"] = False
                    st.rerun()
    elif st.session_state.get("search_executed") and st.session_state.get("match_search", "").strip():
        st.markdown(
            """
            <div class="empty-panel">
                <h3>No he encontrado partidos con esa busqueda</h3>
                <p>Prueba con el nombre de un equipo o una parte del cruce en la fecha seleccionada.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_match_detail_header(match_dashboard: dict, selected_context: dict) -> None:
    match = match_dashboard["match"]
    analysis = match_dashboard["analysis"]
    fecha_label = match.get("match_date") or selected_context["target_date"]
    hora_label = match.get("time") or "Sin hora"
    fuente_label = match.get("source") or "Backend"
    st.markdown(
        f"""
        <div class="toolbar-shell">
            <div class="toolbar-kicker">Match detail</div>
            <div class="toolbar-title">{analysis['local']} vs {analysis['visitante']}</div>
            <div class="toolbar-meta">{analysis['liga']} | {fecha_label} | {hora_label} | Fuente {fuente_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_league_selected_match_card(selected_match: pd.Series | None) -> None:
    if selected_match is None:
        st.markdown(
            """
            <div class="empty-panel">
                <h3>Selecciona un partido para abrir su match detail</h3>
                <p>La vista dedicada concentra resumen ejecutivo, comparativa, proyeccion, jugadores y cuotas sin cargar el analisis completo dentro de la liga.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    hora_label = str(selected_match.get("Time", "") or "").strip() or "Sin hora"
    source_label = selected_match.get("Source") or "Backend"
    match_date = selected_match.get("MatchDate")
    fecha_label = match_date.strftime("%d/%m/%Y") if match_date else "Sin fecha"
    st.markdown(
        f"""
        <div class="panel">
            <div class="signal-label">Partido seleccionado</div>
            <h3>{selected_match['HomeTeam']} vs {selected_match['AwayTeam']}</h3>
            <p>{fecha_label} | {hora_label} | Fuente {source_label}</p>
            <p>Abre la pagina dedicada para ver el detalle completo por tabs y mantener la vista de liga ligera.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_match_detail_view() -> None:
    selected_context = st.session_state.get("selected_match_context")
    if not selected_context:
        st.session_state["current_view"] = "league"
        st.rerun()

    target_date = date.fromisoformat(selected_context["target_date"])
    league = selected_context["league"]
    match_dashboard = get_match_dashboard(
        league,
        target_date,
        selected_context["match_id"],
        st.session_state.get("sportmonks_api_token", ""),
    )
    st.session_state["match_dashboard"] = match_dashboard

    render_match_detail_header(match_dashboard, selected_context)

    action_cols = st.columns([1.1, 1.1, 1.1, 0.8, 0.8])
    with action_cols[0]:
        if st.button("Volver a la liga", use_container_width=True):
            volver_a_liga()
            st.rerun()
    with action_cols[1]:
        if st.button("Ver todas las ligas", use_container_width=True):
            volver_a_ligas()
            st.rerun()
    with action_cols[2]:
        if st.button("Ranking diario", use_container_width=True):
            ir_a_ranking_diario()
            st.rerun()
    with action_cols[3]:
        st.metric("Liga", league)
    with action_cols[4]:
        st.metric("Partido", selected_context["match_id"])

    analisis = match_dashboard["analysis"]
    resultado = analisis["resultado"]
    odds_rows = match_dashboard["odds_rows"]
    signal_flags = match_dashboard["signal_flags"]

    tab_executive, tab_season, tab_compare, tab_projection, tab_players, tab_odds = st.tabs(
        [
            "Resumen ejecutivo",
            "Estadisticas de temporada",
            "Comparativa & H2H",
            "Proyeccion del partido",
            "Jugadores",
            "Cuotas y valor",
        ]
    )

    with tab_executive:
        render_summary_band(analisis)
        render_match_decision_snapshot(analisis, odds_rows)
        render_match_executive_summary(analisis, odds_rows)
        overview_left, overview_right = st.columns([1.25, 1])
        with overview_left:
            st.markdown('<div class="section-title">Quien tiene ventaja</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                render_signal_card(f"Victoria {analisis['local']}", resultado["1"], highlight=signal_flags["1"]["highlight"])
            with c2:
                render_signal_card("Empate", resultado["X"], highlight=signal_flags["X"]["highlight"])
            with c3:
                render_signal_card(f"Victoria {analisis['visitante']}", resultado["2"], highlight=signal_flags["2"]["highlight"])
        with overview_right:
            render_radar_panel(analisis)
        if st.toggle("Ver lectura ampliada", value=False, key=f"show_exec_insights_{selected_context['match_id']}"):
            render_insight_panel(match_dashboard["insights"])

    with tab_season:
        recent_window = analisis["stats_local"].get("recent_window", 10)
        mostrar_overlay_forma = st.toggle(
            f"Mostrar overlay de forma reciente ({recent_window} partidos)",
            value=True,
            key=f"season_overlay_{selected_context['match_id']}",
        )
        st.markdown('<div class="section-title">Base de temporada jugada</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="panel">
                <div class="signal-label">Lectura base</div>
                <p>Por defecto se muestra el escenario que mas pesa en la decision del partido: local en casa y visitante fuera. El resto de despieces queda detras de un toggle para no duplicar lectura.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        eq_1, eq_2 = st.columns(2)
        with eq_1:
            st.markdown(f"### {analisis['local']}")
            render_split_panel("Temporada completa | En casa", analisis["stats_local"]["home"])
        with eq_2:
            st.markdown(f"### {analisis['visitante']}")
            render_split_panel("Temporada completa | Fuera", analisis["stats_visitante"]["away"])

        if st.toggle("Ver despiece completo de temporada", value=False, key=f"season_full_{selected_context['match_id']}"):
            full_left, full_right = st.columns(2)
            with full_left:
                st.markdown(f"### {analisis['local']}")
                render_split_panel("Temporada completa | Global", analisis["stats_local"]["overall"])
                render_split_panel("Temporada completa | Fuera", analisis["stats_local"]["away"])
            with full_right:
                st.markdown(f"### {analisis['visitante']}")
                render_split_panel("Temporada completa | Global", analisis["stats_visitante"]["overall"])
                render_split_panel("Temporada completa | En casa", analisis["stats_visitante"]["home"])

        if mostrar_overlay_forma:
            st.markdown('<div class="section-title">Overlay de forma reciente</div>', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="panel">
                    <div class="signal-label">Capa de timing</div>
                    <p>Este overlay no sustituye la temporada. Relee el cruce con la ventana reciente de {recent_window} partidos para detectar aceleracion, enfriamiento o divergencias frente a la base anual.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            recent_left, recent_right = st.columns(2)
            with recent_left:
                st.markdown(f"### {analisis['local']}")
                render_split_panel(
                    f"Forma reciente | Ultimos {analisis['stats_local'].get('recent_window', recent_window)}",
                    analisis["stats_local"]["recent_overall"],
                )
                render_form_card(analisis["local"], analisis["stats_local"]["form"])
            with recent_right:
                st.markdown(f"### {analisis['visitante']}")
                render_split_panel(
                    f"Forma reciente | Ultimos {analisis['stats_visitante'].get('recent_window', recent_window)}",
                    analisis["stats_visitante"]["recent_overall"],
                )
                render_form_card(analisis["visitante"], analisis["stats_visitante"]["form"])

    with tab_compare:
        st.markdown('<div class="section-title">Comparativa & H2H</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="panel">
                <div class="signal-label">Uso recomendado</div>
                <p>Esta tab sirve para validar si la ventaja base del partido se sostiene al comparar contexto casa/fuera y precedentes. H2H es contexto secundario, no driver principal de entrada.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        compare_left, compare_right = st.columns([1.2, 1])
        with compare_left:
            st.dataframe(pd.DataFrame(match_dashboard["comparison_table"]), use_container_width=True, hide_index=True)
        with compare_right:
            render_h2h_summary_card(analisis["h2h"], analisis["local"], analisis["visitante"])
        if st.toggle("Ver H2H partido a partido", value=False, key=f"h2h_explorer_{selected_context['match_id']}"):
            render_h2h_explorer(analisis["h2h"])

    with tab_projection:
        st.markdown('<div class="section-title">Mercados que cambian decision</div>', unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        with m1:
            render_signal_card("Ambos marcan", resultado["BTTS"], highlight=signal_flags["BTTS"]["highlight"])
        with m2:
            render_signal_card("Over 2.5 goles", resultado["O25"], highlight=signal_flags["O25"]["highlight"])
        with m3:
            render_signal_card("Over 9.5 corners", resultado["Over9.5_Corn"], highlight=signal_flags["Over9.5_Corn"]["highlight"])
        expected_cols = st.columns(2)
        with expected_cols[0]:
            render_expected_card("Total goals", resultado["Total_Goals"], "Media servida por backend")
        with expected_cols[1]:
            render_expected_card("Total corners", resultado["Total_Corners"], "Volumen total esperado")
        if st.toggle("Ver mercados secundarios", value=False, key=f"projection_secondary_{selected_context['match_id']}"):
            s1, s2, s3, s4 = st.columns(4)
            s1.metric(f"{analisis['local']} +1.5 goles", f"{resultado['Home_Over15'] * 100:.1f}%")
            s2.metric(f"{analisis['visitante']} +1.5 goles", f"{resultado['Away_Over15'] * 100:.1f}%")
            s3.metric(f"{analisis['local']} puerta a cero", f"{resultado['Home_CleanSheet'] * 100:.1f}%")
            s4.metric(f"{analisis['visitante']} puerta a cero", f"{resultado['Away_CleanSheet'] * 100:.1f}%")
        if st.toggle("Ver trazabilidad del modelo", value=False, key=f"projection_trace_{selected_context['match_id']}"):
            render_traceability_panel(analisis)

    with tab_players:
        st.markdown('<div class="section-title">Probabilidad de jugadores</div>', unsafe_allow_html=True)
        render_player_props_panel(match_dashboard["player_probabilities"])

    with tab_odds:
        st.markdown('<div class="section-title">Cuotas y valor</div>', unsafe_allow_html=True)
        odds_cols = st.columns(3)
        cuotas_usuario: dict[str, float] = {}
        match_key = safe_key(f"{analisis['local']}_{analisis['visitante']}_{analisis['match_date']}")
        for indice, fila in enumerate(odds_rows):
            with odds_cols[indice % 3]:
                cuotas_usuario[fila["market"]] = st.number_input(
                    f"Cuota {fila['market']}",
                    min_value=1.01,
                    value=float(fila["offered_odds"]),
                    step=0.01,
                    key=f"odd_{match_key}_{safe_key(fila['market'])}",
                )

        filas_comparador = compare_odds(
            [
                {"market": fila["market"], "prob": fila["prob"], "offered_odds": cuotas_usuario[fila["market"]]}
                for fila in odds_rows
            ]
        )
        render_comparador_cuotas(filas_comparador)

        if st.toggle("Ver staking y favoritos", value=False, key=f"odds_advanced_{selected_context['match_id']}"):
            st.markdown("### Stake con Kelly")
            nombres_mercado = [fila["market"] for fila in odds_rows]
            mercado_kelly = st.selectbox("Mercado para stake", nombres_mercado)
            mercado_seleccionado = next(item for item in filas_comparador if item["market"] == mercado_kelly)
            k_left, k_mid, k_right = st.columns(3)
            with k_left:
                bankroll = st.number_input("Bankroll disponible", min_value=1.0, value=100.0, step=10.0)
            with k_mid:
                modo_kelly = st.selectbox("Intensidad Kelly", ["Full Kelly", "Half Kelly", "Quarter Kelly"], index=1)
            with k_right:
                cuota_input = st.number_input(
                    "Cuota usada en Kelly",
                    min_value=1.01,
                    value=float(mercado_seleccionado["offered_odds"]),
                    step=0.01,
                    key=f"kelly_custom_odd_{match_key}_{safe_key(mercado_kelly)}",
                )

            resultado_kelly = calculate_kelly(
                market=mercado_kelly,
                probability=float(mercado_seleccionado["prob"]),
                offered_odds=float(cuota_input),
                bankroll=float(bankroll),
                mode=modo_kelly,
            )
            st.markdown(
                f"""
                <div class="kelly-box">
                    <div class="signal-label">Mercado seleccionado</div>
                    <div class="kelly-main">{mercado_kelly}</div>
                    <div class="kelly-sub">Prob IA {resultado_kelly['probability'] * 100:.2f}% | Cuota justa @{resultado_kelly['fair_odds']:.2f} | Cuota casa @{resultado_kelly['offered_odds']:.2f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            r1, r2, r3 = st.columns(3)
            r1.metric("% bankroll a invertir", f"{resultado_kelly['stake_fraction'] * 100:.2f}%")
            r2.metric("Stake recomendado", f"{resultado_kelly['stake_units']:.2f} u")
            r3.metric("Edge esperado", f"{resultado_kelly['edge'] * 100:.2f}%")

            st.markdown("### Picks favoritos")
            favorite_state = get_favorites()
            acciones_fav = st.columns([1, 1.2, 2])
            with acciones_fav[0]:
                guardar_pick = st.button("Guardar pick favorito", use_container_width=True)
            with acciones_fav[1]:
                limpiar_picks = st.button("Vaciar favoritos", use_container_width=True)
            if guardar_pick:
                create_favorite(
                    {
                        "liga": analisis["liga"],
                        "match": f"{analisis['local']} vs {analisis['visitante']}",
                        "market": mercado_kelly,
                        "prob": resultado_kelly["probability"],
                        "fair_odds": resultado_kelly["fair_odds"],
                        "offered_odds": resultado_kelly["offered_odds"],
                        "edge": resultado_kelly["edge"],
                        "kelly_pct": resultado_kelly["stake_fraction"],
                        "stake_units": resultado_kelly["stake_units"],
                    }
                )
                st.rerun()
            if limpiar_picks:
                clear_favorites()
                st.rerun()

            favoritos = favorite_state["items"]
            resumen_favoritos = favorite_state["summary"]
            if resumen_favoritos["count"] > 0:
                fav_m1, fav_m2, fav_m3 = st.columns(3)
                fav_m1.metric("Picks guardados", str(resumen_favoritos["count"]))
                fav_m2.metric("Stake total", f"{resumen_favoritos['total_stake_units']:.2f} u")
                fav_m3.metric("Edge medio", f"{resumen_favoritos['average_edge'] * 100:.2f}%")
            if favoritos:
                for favorito in favoritos:
                    cols = st.columns([5, 1])
                    with cols[0]:
                        with st.container(border=True):
                            st.write(favorito["market"])
                            st.caption(f"{favorito['match']} | {favorito['liga']}")
                            st.caption(
                                f"Prob IA {favorito['prob'] * 100:.2f}% | Justa @{favorito['fair_odds']:.2f} | Casa @{favorito['offered_odds']:.2f}"
                            )
                            st.caption(
                                f"Edge {favorito['edge'] * 100:.2f}% | Kelly {favorito['kelly_pct'] * 100:.2f}% | Stake {favorito['stake_units']:.2f} u | {favorito['saved_at']}"
                            )
                    with cols[1]:
                        if st.button("Eliminar", key=f"delete_{favorito['id']}", use_container_width=True):
                            delete_favorite(favorito["id"])
                            st.rerun()


def render_daily_value_view(fecha_objetivo: date) -> None:
    competition_view = st.radio(
        "Universo del ranking",
        ["Ligas", "Torneos"],
        key="competition_view",
        horizontal=True,
        label_visibility="collapsed",
    )
    ranking_groups = get_daily_value_ranking(fecha_objetivo, competition_view)

    st.markdown(
        f"""
        <div class="toolbar-shell">
            <div class="toolbar-kicker">Ranking diario independiente</div>
            <div class="toolbar-title">Value bets del {fecha_objetivo.strftime("%d/%m/%Y")}</div>
            <div class="toolbar-meta">Orden interno por edge %, confianza del modelo y tamano de muestra. El tablero separa ligas para no mezclar universos sin normalizar.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="panel">
            <div class="signal-label">Criterio operativo</div>
            <p>La ordenacion se hace dentro de cada liga por edge %, despues por confianza del modelo y despues por tamano de muestra. La confianza se aproxima con la distancia de la probabilidad al punto neutro y la muestra usa el minimo de partidos acumulados entre ambos equipos para mantener un criterio conservador.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_cols = st.columns([1.1, 0.9, 0.9])
    with top_cols[0]:
        if st.button("Volver al explorador", use_container_width=True):
            volver_a_ligas()
            st.rerun()
    with top_cols[1]:
        st.metric("Ligas con picks", len(ranking_groups))
    with top_cols[2]:
        st.metric("Fecha", fecha_objetivo.strftime("%d/%m"))

    if not ranking_groups:
        st.markdown(
            """
            <div class="empty-panel">
                <h3>No hay value bets clasificadas para este universo</h3>
                <p>Prueba con otra fecha o cambia entre ligas y torneos para revisar un conjunto distinto de competiciones.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for grupo in ranking_groups:
        st.markdown(
            f"""
            <div class="ranking-card">
                <div class="ranking-head">
                    <div class="ranking-head-copy">
                        <h3>{grupo['league']}</h3>
                    </div>
                    <div class="ranking-badge">{grupo['country']} | {grupo['match_count']} partidos</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for posicion, fila in enumerate(grupo["picks"], start=1):
            edge_pct = float(fila["edge"]) * 100
            confidence_pct = float(fila.get("confidence", 0.0)) * 100
            sample_size = int(fila.get("sample_size") or 0)
            metric_cols = st.columns([0.65, 2.6, 1, 1, 1, 0.9])
            with metric_cols[0]:
                st.metric("#", str(posicion))
            with metric_cols[1]:
                with st.container(border=True):
                    st.write(f"{fila['match']} | {fila['market']}")
                    st.caption(
                        f"Edge {edge_pct:+.2f}% | Confianza {fila.get('confidence_label', 'N/D')} ({confidence_pct:.1f}%) | Muestra conservadora {sample_size} partidos"
                    )
                    st.caption(
                        f"Prob {float(fila['prob']) * 100:.1f}% | Justa @{float(fila['fair_odds']):.2f} | Casa @{float(fila['offered_odds']):.2f} | {fila.get('provider') or 'Proveedor no informado'}"
                    )
            with metric_cols[2]:
                st.metric("Edge %", f"{edge_pct:+.2f}%")
            with metric_cols[3]:
                st.metric("Confianza", f"{confidence_pct:.1f}%")
            with metric_cols[4]:
                st.metric("Muestra", str(sample_size))
            with metric_cols[5]:
                if st.button(
                    "Abrir",
                    key=f"daily_value_open_{safe_key(grupo['league'])}_{safe_key(fila['match'])}_{safe_key(fila['market'])}_{posicion}",
                    use_container_width=True,
                ):
                    ir_a_detalle_partido(
                        league=grupo["league"],
                        match_id=str(fila["match_id"]),
                        fixture_label=str(fila["match"]),
                        target_date=fecha_objetivo,
                    )
                    st.rerun()


def render_league_view(fecha_objetivo: date, hoy: date) -> None:
    if not st.session_state.get("selected_league"):
        competition_view = st.radio(
            "Tipo de competicion",
            ["Ligas", "Torneos"],
            key="competition_view",
            horizontal=True,
            label_visibility="collapsed",
        )
        portada_ligas = get_leagues(fecha_objetivo, competition_view)
        liga_elegida = render_league_hub(portada_ligas, fecha_objetivo, hoy)
        if liga_elegida:
            st.session_state["selected_league"] = liga_elegida
            st.session_state["current_view"] = "league"
            limpiar_contexto_partido()
            st.rerun()
        st.stop()

    liga_seleccionada = st.session_state["selected_league"]
    league_dashboard = get_league_dashboard(liga_seleccionada, fecha_objetivo)
    st.session_state["league_dashboard"] = league_dashboard

    st.markdown(
        f"""
        <div class="toolbar-shell">
            <div class="toolbar-kicker">Liga activa</div>
            <div class="toolbar-title">{league_dashboard['league']}</div>
            <div class="toolbar-meta">{league_dashboard['country']} | Vista ligera para {fecha_objetivo.strftime("%d/%m/%Y")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_1, top_2, top_3, top_4 = st.columns([1.1, 1.1, 0.7, 0.7])
    with top_1:
        if st.button("Ver todas las ligas", use_container_width=True):
            volver_a_ligas()
            st.rerun()
    with top_2:
        if st.button("Ranking diario", use_container_width=True):
            ir_a_ranking_diario()
            st.rerun()
    with top_3:
        st.metric("Partidos", league_dashboard["match_count"])
    with top_4:
        st.metric("Pais", league_dashboard["country"])

    st.markdown('<div class="layout-divider"></div>', unsafe_allow_html=True)
    layout_left, layout_right = st.columns([1.05, 1.45], gap="large")

    partidos_df = pd.DataFrame(
        [
            {
                "MatchId": item["match_id"],
                "EventId": item["event_id"],
                "Date": item["date"],
                "MatchDate": pd.to_datetime(item["match_date"]).date() if item["match_date"] else fecha_objetivo,
                "Time": item["time"],
                "HomeTeam": item["home_team"],
                "AwayTeam": item["away_team"],
                "HomeTeamRaw": item["home_team_raw"],
                "AwayTeamRaw": item["away_team_raw"],
                "FixtureLabel": item["fixture_label"],
                "Source": item["source"],
            }
            for item in league_dashboard["matches"]
        ]
    )

    with layout_left:
        if not partidos_df.empty:
            partido_seleccionado = render_fixture_cards(partidos_df, fecha_objetivo, hoy)
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

    with layout_right:
        render_league_selected_match_card(partido_seleccionado)
        if partido_seleccionado is not None:
            if st.button("Abrir match detail", key=f"open_detail_{partido_seleccionado['MatchId']}", use_container_width=True):
                ir_a_detalle_partido(
                    league=liga_seleccionada,
                    match_id=str(partido_seleccionado["MatchId"]),
                    fixture_label=str(partido_seleccionado["FixtureLabel"]),
                    target_date=fecha_objetivo,
                )
                st.rerun()
        if league_dashboard["ranking"]:
            render_ranking_value_panel(league_dashboard["ranking"], fecha_objetivo.strftime("%d/%m/%Y"))


for key, default in {
    "solo_hoy_toggle": True,
    "selected_league": None,
    "competition_view": "Ligas",
    "current_view": "league",
    "match_search": "",
    "search_results": [],
    "search_executed": False,
    "sportmonks_api_token": "",
    "match_dashboard": None,
    "league_dashboard": None,
    "selected_match_context": None,
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

with st.expander("Configuracion de Sportmonks", expanded=False):
    st.caption("El token se envia al backend para que resuelva la capa de jugadores; Streamlit ya no consulta proveedores externos.")
    token_cols = st.columns([3.2, 0.8])
    with token_cols[0]:
        token_input = st.text_input(
            "SPORTMONKS_API_TOKEN",
            key="sportmonks_api_token_input",
            type="password",
            value=st.session_state.get("sportmonks_api_token", ""),
            placeholder="Introduce tu token de Sportmonks",
        )
    with token_cols[1]:
        st.markdown('<div class="search-icon-spacer"></div>', unsafe_allow_html=True)
        clear_token = st.button("Limpiar", key="clear_sportmonks_token", use_container_width=True)

    if clear_token:
        st.session_state["sportmonks_api_token"] = ""
        st.session_state["sportmonks_api_token_input"] = ""
        st.rerun()

    st.session_state["sportmonks_api_token"] = token_input.strip()

hoy = datetime.now(APP_TIMEZONE).date()
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

try:
    if buscar_click:
        st.session_state["search_executed"] = True
        if busqueda_partido.strip():
            st.session_state["search_results"] = search_matches(fecha_objetivo, busqueda_partido)
        else:
            st.session_state["search_results"] = []

    render_search_results(st.session_state.get("search_results", []), fecha_objetivo)

    if st.session_state.get("current_view") == "match_detail" and st.session_state.get("selected_match_context"):
        render_match_detail_view()
    elif st.session_state.get("current_view") == "daily_value":
        render_daily_value_view(fecha_objetivo)
    else:
        render_league_view(fecha_objetivo, hoy)
except BackendApiError as exc:
    st.markdown(
        f"""
        <div class="empty-panel">
            <h3>Backend no disponible</h3>
            <p>{exc}</p>
            <p>Configura `BACKEND_API_URL` y `API_AUTH_KEY` para usar Streamlit como cliente fino del backend.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
