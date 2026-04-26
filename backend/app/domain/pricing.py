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


def closing_line_value(offered_odds: float, closing_odds: float) -> tuple[float, float]:
    if offered_odds <= 0 or closing_odds <= 0:
        return 0.0, 0.0
    absolute = offered_odds - closing_odds
    percent = ((offered_odds / closing_odds) - 1.0) * 100
    return absolute, percent


def build_pick(
    *,
    match_id: str,
    market: str,
    selection: str,
    probability: float,
    offered_odds: float,
    provider: str | None = None,
    kelly_multiplier: float = 0.5,
    stake_units: float | None = None,
    closing_odds: float | None = None,
    clv_absolute: float | None = None,
    clv_percent: float | None = None,
    status: str = "open",
    analysis_id: str | None = None,
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
        stake_units=stake_units,
        closing_odds=closing_odds,
        clv_absolute=clv_absolute,
        clv_percent=clv_percent,
        status=status,
        provider=provider,
        analysis_id=analysis_id,
        created_at=created_at or datetime.now(timezone.utc),
    )


def rank_picks(picks: list[Pick], limit: int) -> list[Pick]:
    ordered = sorted(picks, key=lambda item: item.edge, reverse=True)
    return ordered[:limit]
