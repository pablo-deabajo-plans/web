from __future__ import annotations

from backend.app.domain.pricing import expected_edge, fair_odds


def build_value_pick_ranking(items: list[dict], limit: int = 10) -> list[dict]:
    ranking: list[dict] = []
    for item in items:
        analysis = item.get("analysis")
        auto_odds = item.get("auto_odds") or {}
        if not analysis or not auto_odds:
            continue

        for market in analysis.get("mercados", []):
            market_name = market.get("nombre")
            if market_name not in auto_odds:
                continue

            offered_odds = float(auto_odds[market_name]["odds"])
            probability = float(market["prob"])
            ranking.append(
                {
                    "match": f"{analysis['local']} vs {analysis['visitante']}",
                    "market": market_name,
                    "prob": probability,
                    "fair_odds": fair_odds(probability),
                    "offered_odds": offered_odds,
                    "edge": expected_edge(probability, offered_odds),
                    "provider": auto_odds[market_name]["provider"],
                }
            )

    ranking.sort(key=lambda row: row["edge"], reverse=True)
    return ranking[:limit]
