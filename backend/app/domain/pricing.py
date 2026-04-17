from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.app.domain.models import Pick


def fair_odds(probability: float) -> float:
    if probability <= 0:
        return 0.0
    return 1.0 / probability


def expected_edge(probability: float, decimal_odds: float) -> float:
    return (probability * decimal_odds) - 1.0


def kelly_fraction(probability: float, decimal_odds: float) -> float:
    net_odds = decimal_odds - 1.0
    if net_odds <= 0:
        return 0.0
    probability_losing = 1.0 - probability
    stake = ((net_odds * probability) - probability_losing) / net_odds
    return max(0.0, stake)


def build_pick(
    *,
    match_id: str,
    market: str,
    selection: str,
    probability: float,
    offered_odds: float,
    provider: str | None = None,
    kelly_multiplier: float = 0.5,
    pick_id: str | None = None,
    created_at: datetime | None = None,
) -> Pick:
    fair = fair_odds(probability)
    edge = expected_edge(probability, offered_odds)
    stake = kelly_fraction(probability, offered_odds) * kelly_multiplier
    return Pick(
        id=pick_id or str(uuid4()),
        match_id=match_id,
        market=market,
        selection=selection,
        probability=probability,
        fair_odds=fair,
        offered_odds=offered_odds,
        edge=edge,
        stake_fraction=stake,
        provider=provider,
        created_at=created_at or datetime.now(timezone.utc),
    )


def rank_picks(picks: list[Pick], limit: int) -> list[Pick]:
    ordered = sorted(picks, key=lambda item: item.edge, reverse=True)
    return ordered[:limit]
