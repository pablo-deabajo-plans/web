from __future__ import annotations

import difflib
import os
import unicodedata
from datetime import date, datetime
from typing import Any

import httpx

from backend.app.core.logging import get_logger
from backend.app.core.time import utc_now


LOGGER = get_logger(__name__)
BZZOIRO_BASE_URL = "https://sports.bzzoiro.com"
_HTTP_TIMEOUT = 20

# Maps bzzoiro market key → (our market name, {bzzoiro_selection: our_selection})
_MARKET_MAP: dict[str, tuple[str, dict[str, str]]] = {
    "1x2": ("1X2", {"HOME": "HOME", "DRAW": "DRAW", "AWAY": "AWAY"}),
    "btts": ("BTTS", {"YES": "YES", "NO": "NO"}),
    "over_under": ("TOTAL_GOALS", {"OVER_2_5": "OVER_2_5", "UNDER_2_5": "UNDER_2_5"}),
    "total_goals": ("TOTAL_GOALS", {"OVER_2_5": "OVER_2_5", "UNDER_2_5": "UNDER_2_5"}),
}


class BzzoiroProviderError(RuntimeError):
    """Raised when a bzzoiro API request fails."""


def get_bzzoiro_token() -> str:
    return os.getenv("BZZOIRO_API_TOKEN", "").strip()


def _request_json(path: str, *, params: dict[str, Any] | None = None, token: str) -> dict[str, Any]:
    if not token:
        return {}
    try:
        response = httpx.get(
            f"{BZZOIRO_BASE_URL}{path}",
            params=params or {},
            headers={"Authorization": f"Token {token}"},
            timeout=_HTTP_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise BzzoiroProviderError(f"Bzzoiro request failed path={path}") from exc
    except ValueError as exc:
        raise BzzoiroProviderError(f"Bzzoiro response not valid JSON path={path}") from exc


def fetch_bzzoiro_events_for_date(target_date: date, *, token: str | None = None) -> list[dict[str, Any]]:
    tok = token or get_bzzoiro_token()
    if not tok:
        return []
    date_str = target_date.isoformat()
    events: list[dict[str, Any]] = []
    offset = 0
    limit = 100
    while True:
        try:
            payload = _request_json(
                "/api/v2/events/",
                params={"date_from": date_str, "date_to": date_str, "limit": limit, "offset": offset},
                token=tok,
            )
        except BzzoiroProviderError as exc:
            LOGGER.warning("fetch_bzzoiro_events_for_date failed date=%s error=%s", date_str, exc)
            break
        batch = payload.get("results") or []
        events.extend(batch)
        total = int(payload.get("count") or 0)
        if not batch or not payload.get("next") or len(events) >= total:
            break
        offset += limit
    return events


def fetch_bzzoiro_odds_comparison(event_id: int | str, *, token: str | None = None) -> dict[str, Any]:
    tok = token or get_bzzoiro_token()
    if not tok:
        return {}
    try:
        return _request_json(f"/api/v2/events/{event_id}/odds/comparison/", token=tok)
    except BzzoiroProviderError as exc:
        LOGGER.warning("fetch_bzzoiro_odds_comparison failed event_id=%s error=%s", event_id, exc)
        return {}


def _normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFD", name.lower())
    ascii_name = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    for prefix in ("fc ", "cf ", "sc ", "ac ", "as ", "ss ", "us ", "cd ", "ud ", "rcd ", "rc ", "ca ", "ssc ", "afc ", "fk "):
        if ascii_name.startswith(prefix):
            ascii_name = ascii_name[len(prefix):]
            break
    return ascii_name.strip().replace(".", "").replace("-", " ")


def find_bzzoiro_event(
    home_team: str,
    away_team: str,
    bzzoiro_events: list[dict[str, Any]],
    *,
    threshold: float = 0.80,
) -> dict[str, Any] | None:
    norm_home = _normalize_name(home_team)
    norm_away = _normalize_name(away_team)
    best_score = 0.0
    best_match: dict[str, Any] | None = None
    for event in bzzoiro_events:
        bz_home = _normalize_name(str(event.get("home_team", "")))
        bz_away = _normalize_name(str(event.get("away_team", "")))
        home_sim = difflib.SequenceMatcher(None, norm_home, bz_home).ratio()
        away_sim = difflib.SequenceMatcher(None, norm_away, bz_away).ratio()
        if home_sim < threshold or away_sim < threshold:
            continue
        combined = (home_sim + away_sim) / 2
        if combined > best_score:
            best_score = combined
            best_match = event
    return best_match


def parse_bzzoiro_comparison_odds(
    comparison: dict[str, Any],
    *,
    fallback_ts: datetime | None = None,
) -> list[dict[str, Any]]:
    ts = fallback_ts or utc_now()
    snapshots: list[dict[str, Any]] = []
    markets = comparison.get("markets") or {}

    for market_key, (our_market, selection_map) in _MARKET_MAP.items():
        market_data = markets.get(market_key)
        if not market_data or not isinstance(market_data, dict):
            continue
        for bz_selection, our_selection in selection_map.items():
            outcome = market_data.get(bz_selection)
            if not outcome or not isinstance(outcome, dict):
                continue
            bookmakers = outcome.get("bookmakers") or {}
            for bk_slug, bk_data in bookmakers.items():
                if not isinstance(bk_data, dict):
                    continue
                try:
                    odds_float = float(bk_data.get("decimal_odds") or 0)
                except (TypeError, ValueError):
                    continue
                if odds_float <= 1.0:
                    continue
                updated_raw = bk_data.get("updated_at")
                try:
                    quote_ts = (
                        datetime.fromisoformat(str(updated_raw).replace("Z", "+00:00"))
                        if updated_raw
                        else ts
                    )
                except ValueError:
                    quote_ts = ts
                snapshots.append(
                    {
                        "market": our_market,
                        "selection": our_selection,
                        "decimal_odds": odds_float,
                        "sportsbook": bk_slug,
                        "captured_at": quote_ts,
                    }
                )
    return snapshots
