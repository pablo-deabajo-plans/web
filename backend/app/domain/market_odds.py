from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any

from backend.app.domain.analysis import poisson_cdf, poisson_probability_over
from backend.app.domain.models import Analysis, OddsQuote
from backend.app.domain.pricing import expected_edge, fair_odds
from backend.app.domain.pick_generation import normalize_market_selection


PRIMARY_MARKETS = {"1x2", "btts", "total_goals"}
RELIABLE_SECONDARY_BOOKMAKERS = {"draftkings", "fanduel", "betmgm", "caesars", "pinnacle"}


@dataclass(frozen=True)
class CanonicalMarket:
    market_type: str
    scope: str
    side: str | None
    line: float | None
    selection: str


@dataclass(frozen=True)
class OddsComparisonConfig:
    min_edge: float = 0.025
    max_quote_age_hours: int = 48
    secondary_min_bookmakers: int = 2

    def min_probability(self, market_type: str) -> float:
        return {
            "1x2": 0.10,
            "btts": 0.30,
            "total_goals": 0.20,
            "total_corners": 0.20,
            "team_goals": 0.15,
            "team_corners": 0.15,
            "total_cards": 0.20,
        }.get(market_type, 0.20)


def _line_from_token(value: str) -> float | None:
    token = str(value or "").strip().replace(",", ".")
    match = re.search(r"(\d+(?:[._]\d+)?)", token)
    if not match:
        return None
    try:
        return float(match.group(1).replace("_", "."))
    except ValueError:
        return None


def _over_under_selection(selection: str) -> tuple[str, float] | None:
    normalized = re.sub(r"\s+", "_", str(selection or "").strip().upper().replace(".", "_"))
    match = re.search(r"\b(OVER|UNDER|O|U)_?(\d+(?:_\d+)?)\b", normalized)
    if not match:
        return None
    side = "over" if match.group(1) in {"OVER", "O"} else "under"
    line = _line_from_token(match.group(2))
    if line is None:
        return None
    return side, line


def _selection_without_team_prefix(selection: str) -> tuple[str | None, str]:
    normalized = str(selection or "").strip().upper()
    for prefix, side in (("HOME_", "home"), ("AWAY_", "away")):
        if normalized.startswith(prefix):
            return side, normalized[len(prefix) :]
    return None, normalized


def _normalize_market_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(value or "").strip().upper()).strip("_")


def canonical_market_from_quote(quote: OddsQuote, local: str, visitante: str) -> CanonicalMarket | None:
    market = _normalize_market_name(quote.market)
    raw_selection = str(quote.selection or "").strip()
    selection = normalize_market_selection(raw_selection, local, visitante)

    if market in {"1X2", "H2H", "MATCH_WINNER", "MONEYLINE"}:
        if selection in {"HOME", "DRAW", "AWAY"}:
            return CanonicalMarket("1x2", "match", None, None, selection.lower())
        return None

    if market in {"BTTS", "BOTH_TEAMS_TO_SCORE"}:
        if selection in {"YES", "NO"}:
            return CanonicalMarket("btts", "match", None, None, selection.lower())
        return None

    if market in {"TOTAL_GOALS", "TOTALS", "OVER_UNDER", "MATCH_GOALS"}:
        parsed = _over_under_selection(raw_selection)
        if parsed is None:
            return None
        side, line = parsed
        return CanonicalMarket("total_goals", "match", None, line, side)

    if market in {"TOTAL_CORNERS", "CORNERS", "MATCH_CORNERS"}:
        parsed = _over_under_selection(raw_selection)
        if parsed is None:
            return None
        side, line = parsed
        return CanonicalMarket("total_corners", "match", None, line, side)

    if market in {"TOTAL_CARDS", "CARDS", "MATCH_CARDS"}:
        parsed = _over_under_selection(raw_selection)
        if parsed is None:
            return None
        side, line = parsed
        return CanonicalMarket("total_cards", "match", None, line, side)

    if market in {"TEAM_GOALS", "HOME_TEAM_GOALS", "AWAY_TEAM_GOALS"}:
        market_side = "home" if market.startswith("HOME") else ("away" if market.startswith("AWAY") else None)
        selection_side, stripped_selection = _selection_without_team_prefix(raw_selection)
        parsed = _over_under_selection(stripped_selection)
        if parsed is None:
            return None
        side, line = parsed
        team_side = market_side or selection_side
        if team_side not in {"home", "away"}:
            return None
        return CanonicalMarket("team_goals", team_side, team_side, line, side)

    if market in {"TEAM_CORNERS", "HOME_TEAM_CORNERS", "AWAY_TEAM_CORNERS"}:
        market_side = "home" if market.startswith("HOME") else ("away" if market.startswith("AWAY") else None)
        selection_side, stripped_selection = _selection_without_team_prefix(raw_selection)
        parsed = _over_under_selection(stripped_selection)
        if parsed is None:
            return None
        side, line = parsed
        team_side = market_side or selection_side
        if team_side not in {"home", "away"}:
            return None
        return CanonicalMarket("team_corners", team_side, team_side, line, side)

    return None


def _under_probability(mean: float, line: float) -> float:
    return max(0.0, min(1.0, poisson_cdf(mean, int(math.floor(line)))))


def model_probability_for_market(analysis: Analysis, market: CanonicalMarket) -> float | None:
    result = analysis.resultado
    if market.market_type == "1x2":
        return {"home": result.home_win, "draw": result.draw, "away": result.away_win}.get(market.selection)
    if market.market_type == "btts":
        if market.selection == "yes":
            return result.both_teams_score
        if market.selection == "no":
            return 1.0 - result.both_teams_score
        return None

    if market.line is None:
        return None

    mean: float | None = None
    if market.market_type == "total_goals":
        mean = result.total_goals
    elif market.market_type == "total_corners":
        if not _has_match_scope_data(analysis, "has_corners"):
            return None
        mean = result.total_corners
    elif market.market_type == "team_goals":
        mean = analysis.xg_local if market.side == "home" else analysis.xg_visitante
    elif market.market_type == "team_corners":
        if not _has_side_data(analysis, market.side or "", "has_corners"):
            return None
        mean = result.home_corners if market.side == "home" else result.away_corners
    elif market.market_type == "total_cards":
        if not _has_match_scope_data(analysis, "has_cards"):
            return None
        mean = result.total_cards

    if mean is None:
        return None
    if market.selection == "over":
        return poisson_probability_over(float(mean), market.line)
    if market.selection == "under":
        return _under_probability(float(mean), market.line)
    return None


def _has_side_data(analysis: Analysis, side: str, flag: str) -> bool:
    if side == "home":
        return bool(analysis.stats_local.get("home", {}).get(flag, False))
    if side == "away":
        return bool(analysis.stats_visitante.get("away", {}).get(flag, False))
    return False


def _has_match_scope_data(analysis: Analysis, flag: str) -> bool:
    return _has_side_data(analysis, "home", flag) and _has_side_data(analysis, "away", flag)


def _quote_is_fresh(quote: OddsQuote, config: OddsComparisonConfig, now: datetime | None = None) -> bool:
    if quote.captured_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    captured_at = quote.captured_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    return captured_at >= now - timedelta(hours=config.max_quote_age_hours)


def _bookmaker_name(quote: OddsQuote) -> str:
    return str(quote.sportsbook or "").strip()


def _bookmaker_count(quotes: Sequence[OddsQuote]) -> int:
    return len({_bookmaker_name(quote).lower() for quote in quotes if _bookmaker_name(quote)})


def _is_reliable_secondary_provider(bookmaker: str | None) -> bool:
    return str(bookmaker or "").strip().lower() in RELIABLE_SECONDARY_BOOKMAKERS


def _display_market(analysis: Analysis, market: CanonicalMarket) -> str:
    if market.market_type == "1x2":
        return {"home": f"Victoria {analysis.local}", "draw": "Empate", "away": f"Victoria {analysis.visitante}"}[market.selection]
    if market.market_type == "btts":
        return "Ambos marcan" if market.selection == "yes" else "No marcan ambos"

    side_label = "Over" if market.selection == "over" else "Under"
    line = f"{market.line:.1f}" if market.line is not None else ""
    if market.market_type == "total_goals":
        return f"{side_label} {line} goles"
    if market.market_type == "total_corners":
        return f"{side_label} {line} corners"
    if market.market_type == "team_goals":
        team = analysis.local if market.side == "home" else analysis.visitante
        return f"{team} {side_label} {line} goles"
    if market.market_type == "team_corners":
        team = analysis.local if market.side == "home" else analysis.visitante
        return f"{team} {side_label} {line} corners"
    if market.market_type == "total_cards":
        return f"{side_label} {line} tarjetas"
    return market.market_type


def _quote_audit_payload(quote: OddsQuote, market: CanonicalMarket) -> dict[str, Any]:
    return {
        "bookmaker": quote.sportsbook,
        "odds": float(quote.decimal_odds),
        "captured_at": quote.captured_at,
        "market": quote.market,
        "selection": quote.selection,
        "canonical": market,
    }


def compare_analysis_to_quotes(
    analysis: Analysis,
    quotes: Sequence[OddsQuote],
    config: OddsComparisonConfig | None = None,
) -> list[dict]:
    config = config or OddsComparisonConfig()
    grouped: dict[CanonicalMarket, list[OddsQuote]] = {}
    for quote in quotes:
        if float(quote.decimal_odds) <= 1.0 or not _quote_is_fresh(quote, config):
            continue
        canonical = canonical_market_from_quote(quote, analysis.local, analysis.visitante)
        if canonical is None:
            continue
        grouped.setdefault(canonical, []).append(quote)

    rows: list[dict] = []
    for canonical, market_quotes in grouped.items():
        probability = model_probability_for_market(analysis, canonical)
        if probability is None or probability < config.min_probability(canonical.market_type):
            continue

        market_quotes = sorted(
            market_quotes,
            key=lambda quote: (float(quote.decimal_odds), quote.captured_at or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
        best_quote = market_quotes[0]
        bookmaker_count = _bookmaker_count(market_quotes)
        if canonical.market_type not in PRIMARY_MARKETS:
            if bookmaker_count < config.secondary_min_bookmakers and not _is_reliable_secondary_provider(best_quote.sportsbook):
                continue

        best_odds = float(best_quote.decimal_odds)
        edge = expected_edge(probability, best_odds)
        if edge < config.min_edge:
            continue

        rows.append(
            {
                "market": _display_market(analysis, canonical),
                "prob": probability,
                "fair_odds": fair_odds(probability),
                "offered_odds": best_odds,
                "best_odds": best_odds,
                "edge": edge,
                "provider": best_quote.sportsbook,
                "bookmaker": best_quote.sportsbook,
                "number_of_bookmakers": bookmaker_count,
                "captured_at": best_quote.captured_at,
                "canonical_market": canonical,
                "quote_audit": [_quote_audit_payload(quote, canonical) for quote in market_quotes],
            }
        )

    rows.sort(key=lambda item: (item["edge"], item["number_of_bookmakers"], item["prob"]), reverse=True)
    return rows


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
    resolved: dict[str, dict] = {}
    for row in compare_analysis_to_quotes(analysis, quotes, OddsComparisonConfig(min_edge=-1.0, secondary_min_bookmakers=1)):
        resolved[row["market"]] = {
            "odds": row["best_odds"],
            "provider": row["provider"],
            "source": "external",
            "captured_at": row["captured_at"],
            "market": row["canonical_market"].market_type,
            "selection": row["canonical_market"].selection,
            "number_of_bookmakers": row["number_of_bookmakers"],
            "quote_audit": row["quote_audit"],
        }
    return resolved


def external_odds_map_for_teams(local: str, visitante: str, quotes: Sequence[OddsQuote]) -> dict[str, dict]:
    # Kept for legacy dictionary-based analyses; strict canonical matching requires Analysis means.
    key_map = market_quote_key_map_for_teams(local, visitante)
    resolved: dict[str, dict] = {}
    indexed: dict[tuple[str, str], OddsQuote] = {}
    for quote in quotes:
        market_name = str(quote.market or "").strip().upper()
        selection_name = normalize_market_selection(str(quote.selection or "").strip(), local, visitante)
        key = (market_name, selection_name)
        existing = indexed.get(key)
        if existing is None or float(quote.decimal_odds) > float(existing.decimal_odds):
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
            "number_of_bookmakers": 1,
            "quote_audit": [_quote_audit_payload(quote, CanonicalMarket(lookup_key[0].lower(), "match", None, None, lookup_key[1].lower()))],
        }
    return resolved
