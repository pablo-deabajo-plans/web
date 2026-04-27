from __future__ import annotations

from collections.abc import Sequence

from backend.app.domain.models import Analysis, OddsQuote
from backend.app.domain.pick_generation import normalize_market_selection


def market_quote_key_map_for_teams(local: str, visitante: str) -> dict[str, tuple[str, str]]:
    return {
        f"Victoria {local}": ("1X2", "HOME"),
        "Empate": ("1X2", "DRAW"),
        f"Victoria {visitante}": ("1X2", "AWAY"),
        "Ambos marcan": ("BTTS", "YES"),
        "No marcan ambos": ("BTTS", "NO"),
        "Over 2.5 goles": ("TOTAL_GOALS", "OVER_2_5"),
        "Under 2.5 goles": ("TOTAL_GOALS", "UNDER_2_5"),
    }


def market_quote_key_map(analysis: Analysis) -> dict[str, tuple[str, str]]:
    return market_quote_key_map_for_teams(analysis.local, analysis.visitante)


def latest_best_quote_index(quotes: Sequence[OddsQuote], analysis: Analysis) -> dict[tuple[str, str], OddsQuote]:
    indexed: dict[tuple[str, str], OddsQuote] = {}
    for quote in quotes:
        market_name = str(quote.market or "").strip().upper()
        selection_name = normalize_market_selection(str(quote.selection or "").strip(), analysis.local, analysis.visitante)
        key = (market_name, selection_name)
        existing = indexed.get(key)
        if existing is None:
            indexed[key] = quote
            continue
        existing_odds = float(existing.decimal_odds)
        candidate_odds = float(quote.decimal_odds)
        if candidate_odds > existing_odds:
            indexed[key] = quote
            continue
        if candidate_odds == existing_odds and (quote.captured_at or 0) > (existing.captured_at or 0):
            indexed[key] = quote
    return indexed


def external_odds_map_for_analysis(analysis: Analysis, quotes: Sequence[OddsQuote]) -> dict[str, dict]:
    key_map = market_quote_key_map(analysis)
    quote_index = latest_best_quote_index(quotes, analysis)
    resolved: dict[str, dict] = {}
    for market_name, lookup_key in key_map.items():
        quote = quote_index.get(lookup_key)
        if quote is None:
            continue
        resolved[market_name] = {
            "odds": float(quote.decimal_odds),
            "provider": quote.sportsbook,
            "source": "external",
            "captured_at": quote.captured_at,
            "market": quote.market,
            "selection": quote.selection,
        }
    return resolved


def external_odds_map_for_teams(local: str, visitante: str, quotes: Sequence[OddsQuote]) -> dict[str, dict]:
    key_map = market_quote_key_map_for_teams(local, visitante)
    resolved: dict[str, dict] = {}
    indexed: dict[tuple[str, str], OddsQuote] = {}
    for quote in quotes:
        market_name = str(quote.market or "").strip().upper()
        selection_name = normalize_market_selection(str(quote.selection or "").strip(), local, visitante)
        key = (market_name, selection_name)
        existing = indexed.get(key)
        if existing is None:
            indexed[key] = quote
            continue
        existing_odds = float(existing.decimal_odds)
        candidate_odds = float(quote.decimal_odds)
        if candidate_odds > existing_odds or (
            candidate_odds == existing_odds and (quote.captured_at or 0) > (existing.captured_at or 0)
        ):
            indexed[key] = quote
    for market_name, lookup_key in key_map.items():
        quote = indexed.get(lookup_key)
        if quote is None:
            continue
        resolved[market_name] = {
            "odds": float(quote.decimal_odds),
            "provider": quote.sportsbook,
            "source": "external",
            "captured_at": quote.captured_at,
            "market": quote.market,
            "selection": quote.selection,
        }
    return resolved
