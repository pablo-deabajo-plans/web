from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from backend.app.domain.models import (
    ACTIVE_MATCH_STATUSES,
    MATCH_STATUS_ABANDONED,
    MATCH_STATUS_CANCELLED,
    MATCH_STATUS_FINISHED,
    SETTLED_MATCH_STATUSES,
    VOID_MATCH_STATUSES,
)


MONEY_PRECISION = Decimal("0.0001")


@dataclass(frozen=True)
class SettlementDecision:
    status: str
    settled_selection: str
    profit_units: Decimal


def normalize_text(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("_", " ")
    return " ".join(normalized.split())


def normalize_match_status(value: str) -> str:
    normalized = normalize_text(value).replace("-", " ")
    legacy_map = {
        "completed": MATCH_STATUS_FINISHED,
        "final": MATCH_STATUS_FINISHED,
        "full time": MATCH_STATUS_FINISHED,
        "post": MATCH_STATUS_FINISHED,
        "closed": MATCH_STATUS_FINISHED,
        "canceled": MATCH_STATUS_CANCELLED,
        "suspended": MATCH_STATUS_ABANDONED,
        "no contest": MATCH_STATUS_ABANDONED,
    }
    return legacy_map.get(normalized, normalized)


def _void_decision(reason: str = "void") -> SettlementDecision:
    return SettlementDecision(status="void", settled_selection=reason, profit_units=Decimal("0.0000"))


def profit_for_status(status: str, stake_units: Decimal, offered_odds: Decimal) -> Decimal:
    if status == "won":
        return (stake_units * (offered_odds - Decimal("1"))).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)
    if status in {"push", "void"}:
        return Decimal("0.0000")
    return (stake_units * Decimal("-1")).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _normalize_1x2_selection(selection: str, home_team: str, away_team: str) -> str:
    normalized = normalize_text(selection)
    if normalized in {"home", normalize_text(home_team), normalize_text(f"victoria {home_team}")}:
        return "HOME"
    if normalized in {"away", normalize_text(away_team), normalize_text(f"victoria {away_team}")}:
        return "AWAY"
    if normalized in {"draw", "x", "empate"}:
        return "DRAW"
    return normalized.upper()


def _normalize_btts_selection(selection: str) -> str:
    normalized = normalize_text(selection)
    if normalized in {"yes", "si", "sí", "ambos marcan", "btts"}:
        return "YES"
    if normalized in {"no", "no marcan ambos"}:
        return "NO"
    return normalized.upper()


def _normalize_total_goals_selection(selection: str) -> str:
    normalized = normalize_text(selection)
    if normalized in {"over 2.5", "over 2 5", "over_2_5", "mas de 2.5", "over 2.5 goles"}:
        return "OVER_2_5"
    if normalized in {"under 2.5", "under 2 5", "under_2_5", "menos de 2.5", "under 2.5 goles"}:
        return "UNDER_2_5"
    return normalized.upper()


def settle_market_pick(
    *,
    match_status: str,
    home_team: str,
    away_team: str,
    home_score: int | None,
    away_score: int | None,
    market: str,
    selection: str,
    stake_units: Decimal,
    offered_odds: Decimal,
) -> SettlementDecision | None:
    normalized_status = normalize_match_status(match_status)
    if normalized_status in VOID_MATCH_STATUSES:
        return _void_decision("match_void")

    if normalized_status not in SETTLED_MATCH_STATUSES:
        if normalized_status not in ACTIVE_MATCH_STATUSES:
            return None
        return None

    if home_score is None or away_score is None:
        return _void_decision("missing_score")

    if stake_units <= Decimal("0") or offered_odds <= Decimal("1"):
        return _void_decision("invalid_pick_data")

    market_key = normalize_text(market)

    if market_key == "1x2":
        settled_selection = "HOME" if home_score > away_score else "AWAY" if away_score > home_score else "DRAW"
        selected = _normalize_1x2_selection(selection, home_team, away_team)
        status = "won" if selected == settled_selection else "lost"
        return SettlementDecision(
            status=status,
            settled_selection=settled_selection,
            profit_units=profit_for_status(status, stake_units, offered_odds),
        )

    if market_key == "btts":
        settled_selection = "YES" if home_score > 0 and away_score > 0 else "NO"
        selected = _normalize_btts_selection(selection)
        status = "won" if selected == settled_selection else "lost"
        return SettlementDecision(
            status=status,
            settled_selection=settled_selection,
            profit_units=profit_for_status(status, stake_units, offered_odds),
        )

    if market_key == "total goals":
        settled_selection = "OVER_2_5" if (home_score + away_score) > 2.5 else "UNDER_2_5"
        selected = _normalize_total_goals_selection(selection)
        status = "won" if selected == settled_selection else "lost"
        return SettlementDecision(
            status=status,
            settled_selection=settled_selection,
            profit_units=profit_for_status(status, stake_units, offered_odds),
        )

    return _void_decision("unsupported_market")

