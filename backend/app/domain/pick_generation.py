from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from backend.app.domain.models import Analysis
from backend.app.domain.pricing import build_pick, kelly_fraction


MODEL_VERSION = "legacy-poisson-v1"
KELLY_MULTIPLIER = 0.5


def analysis_id_for_match(match_id: str, model_version: str = MODEL_VERSION) -> str:
    return str(uuid5(NAMESPACE_URL, f"analysis:{model_version}:{match_id}"))


def pick_id_for_match(match_id: str, market: str, selection: str, model_version: str = MODEL_VERSION) -> str:
    return str(uuid5(NAMESPACE_URL, f"pick:{match_id}:{market}:{selection}:{model_version}"))


def normalize_market_selection(selection_name: str, home_team: str, away_team: str) -> str:
    normalized_selection = str(selection_name or "").strip()
    if normalized_selection == home_team:
        return "HOME"
    if normalized_selection == away_team:
        return "AWAY"
    normalized_upper = normalized_selection.upper()
    if normalized_upper in {"HOME", "DRAW", "AWAY", "YES", "NO", "OVER_2_5", "UNDER_2_5"}:
        return normalized_upper
    if normalized_selection in {"Empate", "X"}:
        return "DRAW"
    return normalized_upper


def quote_index(quotes, home_team: str, away_team: str) -> dict[tuple[str, str], object]:
    indexed = {}
    for quote in quotes:
        market_name = str(quote.market or "").strip().upper()
        selection_name = normalize_market_selection(str(quote.selection or "").strip(), home_team, away_team)
        key = (market_name, selection_name)
        existing = indexed.get(key)
        if existing is None or getattr(quote, "captured_at", None) > getattr(existing, "captured_at", None):
            indexed[key] = quote
    return indexed


def stake_units_for_pick(probability: float, offered_odds: float, kelly_multiplier: float = KELLY_MULTIPLIER) -> float:
    stake_fraction = kelly_fraction(probability, offered_odds) * kelly_multiplier
    return round(max(0.0, stake_fraction), 4)


def build_picks_for_analysis(match, analysis: Analysis, analysis_id: str, quotes, *, model_version: str = MODEL_VERSION) -> tuple[list, str | None]:
    from backend.app.domain.market_odds import compare_analysis_to_quotes

    comparison_rows = compare_analysis_to_quotes(analysis, quotes)
    picks = []

    for row in comparison_rows:
        canonical = row["canonical_market"]
        market_name = "1X2" if canonical.market_type == "1x2" else canonical.market_type.upper()
        selection = canonical.selection.upper()
        if canonical.line is not None:
            selection = f"{selection}_{canonical.line:.1f}".replace(".", "_")
        if canonical.side:
            selection = f"{canonical.side.upper()}_{selection}"

        probability = float(row["prob"])
        offered_odds = float(row["best_odds"])
        stake_units = stake_units_for_pick(probability, offered_odds)
        if stake_units <= 0:
            continue

        pick = build_pick(
            pick_id=pick_id_for_match(match.id, market_name, selection, model_version),
            match_id=match.id,
            analysis_id=analysis_id,
            market=market_name,
            selection=selection,
            probability=probability,
            offered_odds=offered_odds,
            provider=row["provider"],
            kelly_multiplier=KELLY_MULTIPLIER,
            stake_units=stake_units,
        )
        if pick.edge <= 0:
            continue
        picks.append(pick)
    if not quotes:
        return [], "missing_odds"
    if not picks:
        return [], "non_actionable"
    return picks, None
