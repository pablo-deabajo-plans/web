from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.app.domain.models import User


PLAN_FREE = "free"
PLAN_PRO = "pro"

FREE_LEAGUES = frozenset(
    {
        "Premier League",
        "LaLiga",
        "Serie A",
        "Bundesliga",
        "Ligue 1",
    }
)

FREE_MATCH_TABS = frozenset({"summary", "projection", "season", "compare", "players"})
PRO_MATCH_TABS = frozenset({"summary", "projection", "odds", "season", "compare", "players"})

FREE_PROJECTION_STATS = frozenset({"goals", "corners"})
FREE_PROJECTION_MIN_PROBABILITY = 0.50
FREE_PROJECTION_MAX_ROWS_PER_SCOPE = 6
FREE_PROJECTION_SCOPES = frozenset({"total"})

UPGRADE_FEATURES = {
    "daily_value": {
        "label": "Ranking diario completo",
        "description": "Ranking global de oportunidades de valor por liga y torneo.",
    },
    "league_value_ranking": {
        "label": "Ranking de valor de la liga",
        "description": "Ordenacion de picks de la liga por edge frente a cuotas reales.",
    },
    "odds_value": {
        "label": "Cuotas y valor",
        "description": "Comparacion modelo vs cuotas reales, cuota justa, provider y edge.",
    },
    "all_leagues": {
        "label": "Todas las ligas y torneos",
        "description": "Cobertura completa fuera de las cinco grandes ligas del plan Free.",
    },
    "advanced_projection": {
        "label": "Distribuciones avanzadas",
        "description": "Umbrales completos por total, local y visitante con mas mercados.",
    },
}


@dataclass(frozen=True)
class PlanAccess:
    plan: str
    is_pro: bool
    free_leagues: frozenset[str] = FREE_LEAGUES

    @property
    def can_view_daily_value(self) -> bool:
        return self.is_pro

    @property
    def can_view_odds_value(self) -> bool:
        return self.is_pro

    @property
    def can_view_all_leagues(self) -> bool:
        return self.is_pro

    @property
    def allowed_match_tabs(self) -> frozenset[str]:
        return PRO_MATCH_TABS if self.is_pro else FREE_MATCH_TABS

    def can_view_league(self, league: str) -> bool:
        return self.is_pro or league in self.free_leagues

    def filter_league_rows(self, rows: Iterable[dict]) -> list[dict]:
        if self.is_pro:
            return list(rows)
        return [row for row in rows if self.can_view_league(str(row.get("league", "")))]

    def filter_matches(self, rows: Iterable[dict]) -> list[dict]:
        if self.is_pro:
            return list(rows)
        return [row for row in rows if self.can_view_league(str(row.get("league", "")))]

    def coerce_match_tab(self, tab: str, fallback: str = "summary") -> str:
        if tab in self.allowed_match_tabs:
            return tab
        return fallback

    def coerce_projection_stat(self, stat: str) -> str:
        if self.is_pro or stat in FREE_PROJECTION_STATS:
            return stat
        return "corners"

    def coerce_projection_min_probability(self, value: float) -> float:
        if self.is_pro:
            return value
        return max(FREE_PROJECTION_MIN_PROBABILITY, value)

    def filter_projection_distribution(self, distribution: dict) -> dict:
        if self.is_pro:
            return distribution

        limited_scopes = []
        for scope in distribution.get("scopes", []):
            if str(scope.get("key", "")) not in FREE_PROJECTION_SCOPES:
                continue
            limited_scope = dict(scope)
            limited_scope["rows"] = list(limited_scope.get("rows", []))[:FREE_PROJECTION_MAX_ROWS_PER_SCOPE]
            limited_scopes.append(limited_scope)

        result = dict(distribution)
        result["scopes"] = limited_scopes
        result["has_rows"] = any(scope.get("available") for scope in limited_scopes)
        result["is_limited"] = True
        return result


def access_for_user(user: User | None) -> PlanAccess:
    plan = str(user.plan if user is not None else PLAN_FREE).strip().lower()
    if plan != PLAN_PRO:
        plan = PLAN_FREE
    return PlanAccess(plan=plan, is_pro=plan == PLAN_PRO)


def upgrade_feature_context(feature: str | None) -> dict[str, str]:
    return UPGRADE_FEATURES.get(str(feature or ""), UPGRADE_FEATURES["daily_value"])
