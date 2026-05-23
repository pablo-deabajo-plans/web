from __future__ import annotations

from collections.abc import Sequence

from backend.app.domain.market_odds import compare_analysis_to_quotes, external_odds_map_for_teams
from backend.app.domain.models import Analysis
from backend.app.domain.pricing import expected_edge, fair_odds

MIN_EDGE = 0.025  # minimum edge (2.5%) required to include a market in the ranking


def _confidence_score(probability: float) -> float:
    return abs(float(probability) - 0.5) * 2.0


def _confidence_label(score: float) -> str:
    if score >= 0.45:
        return "Alta"
    if score >= 0.25:
        return "Media"
    return "Baja"


def _sample_size(raw_analysis: Analysis | dict) -> int:
    if isinstance(raw_analysis, Analysis):
        stats_local = raw_analysis.stats_local
        stats_visitante = raw_analysis.stats_visitante
    else:
        stats_local = dict(raw_analysis.get("stats_local") or {})
        stats_visitante = dict(raw_analysis.get("stats_visitante") or {})
    local_pj = int((stats_local.get("overall") or {}).get("pj") or 0)
    visitante_pj = int((stats_visitante.get("overall") or {}).get("pj") or 0)
    return min(local_pj, visitante_pj)


def _external_market_odds(raw_analysis: Analysis | dict, quotes: Sequence | None) -> dict[str, dict]:
    if not quotes:
        return {}
    if isinstance(raw_analysis, Analysis):
        return {}
    return external_odds_map_for_teams(
        str(raw_analysis.get("local", "")),
        str(raw_analysis.get("visitante", "")),
        quotes,
    )


def build_value_pick_ranking(items: list[dict], limit: int = 10) -> list[dict]:
    ranking: list[dict] = []
    for item in items:
        raw_analysis = item.get("analysis")
        quotes = item.get("quotes")
        if not raw_analysis or not quotes:
            continue

        if isinstance(raw_analysis, Analysis):
            local = raw_analysis.local
            visitante = raw_analysis.visitante
            comparison_rows = compare_analysis_to_quotes(raw_analysis, quotes)
        else:
            local = str(raw_analysis.get("local", ""))
            visitante = str(raw_analysis.get("visitante", ""))
            market_odds = _external_market_odds(raw_analysis, quotes)
            markets = [
                (str(market.get("nombre", "")), float(market.get("prob", 0.0)))
                for market in raw_analysis.get("mercados", [])
            ]
            comparison_rows = []
            for market_name, probability in markets:
                if market_name not in market_odds:
                    continue
                offered_odds = float(market_odds[market_name]["odds"])
                edge = expected_edge(probability, offered_odds)
                if edge < MIN_EDGE:
                    continue
                comparison_rows.append(
                    {
                        "market": market_name,
                        "prob": probability,
                        "fair_odds": fair_odds(probability),
                        "offered_odds": offered_odds,
                        "edge": edge,
                        "provider": market_odds[market_name]["provider"],
                        "number_of_bookmakers": market_odds[market_name].get("number_of_bookmakers", 1),
                        "captured_at": market_odds[market_name].get("captured_at"),
                    }
                )

        sample_size = _sample_size(raw_analysis)
        for row in comparison_rows:
            probability = float(row["prob"])
            confidence = _confidence_score(probability)
            ranking.append(
                {
                    "league": item.get("league", ""),
                    "country": item.get("country", ""),
                    "match": f"{local} vs {visitante}",
                    "match_id": str(item.get("match_id", "")),
                    "market": row["market"],
                    "prob": probability,
                    "fair_odds": row["fair_odds"],
                    "offered_odds": row["offered_odds"],
                    "edge": row["edge"],
                    "confidence": confidence,
                    "confidence_label": _confidence_label(confidence),
                    "sample_size": sample_size,
                    "provider": row["provider"],
                    "number_of_bookmakers": row.get("number_of_bookmakers", 1),
                    "captured_at": row.get("captured_at"),
                }
            )

    ranking.sort(key=lambda row: (row["edge"], row["confidence"], row["sample_size"]), reverse=True)
    return ranking[:limit]
