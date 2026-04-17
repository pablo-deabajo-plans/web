from backend.app.domain.analysis import (
    DEFAULT_CARDS_AGAINST,
    DEFAULT_CARDS_FOR,
    DEFAULT_CORNERS_AGAINST,
    DEFAULT_CORNERS_FOR,
    DEFAULT_SHOTS_AGAINST,
    DEFAULT_SHOTS_FOR,
    DEFAULT_SHOTS_ON_TARGET_AGAINST,
    DEFAULT_SHOTS_ON_TARGET_FOR,
    LIGAS_FASE_ELIMINATORIA,
    SIMULACIONES,
    VALUE_BET_THRESHOLD,
    build_fallback_h2h as construir_fallback_h2h,
    build_insights as construir_insights,
    build_markets as construir_mercados,
    build_match_analysis as guardar_analisis,
    build_traceability as construir_trazabilidad,
    calculate_contextual_h2h_adjustment as calcular_ajuste_h2h_contextual,
    calculate_knockout_home_bonus as calcular_bonus_eliminatoria_casa,
    is_home_knockout_bonus_applicable as es_fase_eliminatoria_casa,
    model_value as valor_modelo,
    offensive_model_value as valor_modelo_ofensivo,
    simulate_match as simular_partido,
)
from backend.app.domain.player_props import (
    PLAYER_PROP_CONFIG,
    build_player_probabilities as construir_probabilidades_jugadores,
    classify_player_confidence as _clasificar_confianza_jugador,
    poisson_probability_over as _poisson_probabilidad_superar,
    weighted_mean as _media_ponderada,
)
from backend.app.domain.pricing import fair_odds as cuota_justa, kelly_fraction as stake_kelly
from backend.app.services.value_pick_ranking import build_value_pick_ranking


def construir_ranking_value_bets(items: list[dict], limite: int = 10) -> list[dict]:
    return build_value_pick_ranking(items, limit=limite)


__all__ = [
    "DEFAULT_CARDS_AGAINST",
    "DEFAULT_CARDS_FOR",
    "DEFAULT_CORNERS_AGAINST",
    "DEFAULT_CORNERS_FOR",
    "DEFAULT_SHOTS_AGAINST",
    "DEFAULT_SHOTS_FOR",
    "DEFAULT_SHOTS_ON_TARGET_AGAINST",
    "DEFAULT_SHOTS_ON_TARGET_FOR",
    "LIGAS_FASE_ELIMINATORIA",
    "PLAYER_PROP_CONFIG",
    "SIMULACIONES",
    "VALUE_BET_THRESHOLD",
    "_clasificar_confianza_jugador",
    "_media_ponderada",
    "_poisson_probabilidad_superar",
    "calcular_ajuste_h2h_contextual",
    "calcular_bonus_eliminatoria_casa",
    "construir_fallback_h2h",
    "construir_insights",
    "construir_mercados",
    "construir_probabilidades_jugadores",
    "construir_ranking_value_bets",
    "construir_trazabilidad",
    "cuota_justa",
    "es_fase_eliminatoria_casa",
    "guardar_analisis",
    "simular_partido",
    "stake_kelly",
    "valor_modelo",
    "valor_modelo_ofensivo",
]
