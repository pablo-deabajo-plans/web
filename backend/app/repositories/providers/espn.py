from __future__ import annotations

from datetime import date, datetime, timezone, tzinfo
from typing import Any
import httpx

from backend.app.core.logging import get_logger
from backend.app.core.time import UTC, utc_now, utc_today
from backend.app.domain.models import (
    MATCH_STATUS_ABANDONED,
    MATCH_STATUS_CANCELLED,
    MATCH_STATUS_FINISHED,
    MATCH_STATUS_LIVE,
    MATCH_STATUS_POSTPONED,
    MATCH_STATUS_SCHEDULED,
)


LOGGER = get_logger(__name__)
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
DEFAULT_TIMEZONE = UTC


class ESPNProviderError(RuntimeError):
    """Base exception for ESPN provider failures."""


class ESPNRequestError(ESPNProviderError):
    """Raised when the ESPN API request fails."""


class ESPNResponseError(ESPNProviderError):
    """Raised when the ESPN payload cannot be parsed safely."""


def _request_json(url: str, *, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    try:
        response = httpx.get(url, params=params, headers=HTTP_HEADERS, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ESPNRequestError(f"ESPN request failed for url={url} params={params}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ESPNResponseError(f"ESPN response was not valid JSON for url={url}") from exc

    if not isinstance(payload, dict):
        raise ESPNResponseError(f"ESPN response must be a JSON object for url={url}")
    return payload


def _parse_event_datetime(value: str, timezone: tzinfo) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ESPNResponseError(f"Invalid ESPN event date: {value!r}") from exc


def _extract_team_stat(competitor: dict[str, Any], keys: list[str]) -> float | None:
    statistics = competitor.get("statistics") or []
    for entry in statistics:
        name = str((entry or {}).get("name", "")).strip()
        abbreviation = str((entry or {}).get("abbreviation", "")).strip()
        if name not in keys and abbreviation not in keys:
            continue
        value = (entry or {}).get("value", (entry or {}).get("displayValue"))
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _parse_score(value: Any) -> int | None:
    if str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_decimal(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _american_to_decimal(value: Any) -> float | None:
    american = _parse_decimal(value)
    if american in {None, 0.0}:
        return None
    if american > 0:
        return 1 + (american / 100)
    return 1 + (100 / abs(american))


def _to_decimal_odds(value: Any) -> float | None:
    parsed = _parse_decimal(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        return parsed
    return _american_to_decimal(value)


def _normalize_status_token(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    return " ".join(normalized.split())


def _normalize_match_status(*, completed: bool, candidates: list[Any]) -> str:
    normalized_candidates = [_normalize_status_token(candidate) for candidate in candidates if str(candidate or "").strip()]

    if any(
        token in {
            "cancelled",
            "canceled",
            "status canceled",
            "status cancelled",
            "game canceled",
            "match canceled",
            "match cancelled",
        }
        for token in normalized_candidates
    ):
        return MATCH_STATUS_CANCELLED

    if any(
        token in {
            "postponed",
            "status postponed",
            "delayed",
            "rain delayed",
        }
        for token in normalized_candidates
    ):
        return MATCH_STATUS_POSTPONED

    if any(
        token in {
            "abandoned",
            "suspended",
            "status suspended",
            "interrupted",
            "no contest",
        }
        for token in normalized_candidates
    ):
        return MATCH_STATUS_ABANDONED

    if completed or any(
        token in {
            "post",
            "final",
            "full time",
            "finished",
            "complete",
            "closed",
        }
        for token in normalized_candidates
    ):
        return MATCH_STATUS_FINISHED

    if any(
        token in {
            "in",
            "live",
            "pre half",
            "halftime",
            "status halftime",
            "status in progress",
            "in progress",
        }
        for token in normalized_candidates
    ):
        return MATCH_STATUS_LIVE

    return MATCH_STATUS_SCHEDULED


def _extract_primary_odds(summary: dict[str, Any]) -> dict[str, Any]:
    competition = ((summary.get("header", {}) or {}).get("competitions") or [{}])[0]
    odds_header = competition.get("odds") or []
    odds_root = summary.get("odds") or []
    primary = odds_header[0] if odds_header else (odds_root[0] if odds_root else {})
    return primary if isinstance(primary, dict) else {}


def _parse_captured_at(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_scoreboard_event(
    event: dict[str, Any],
    *,
    source: str,
    timezone: tzinfo = DEFAULT_TIMEZONE,
) -> dict[str, Any] | None:
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []
    home = next((item for item in competitors if item.get("homeAway") == "home"), None)
    away = next((item for item in competitors if item.get("homeAway") == "away"), None)
    if not home or not away:
        return None

    event_date = _parse_event_datetime(str(event.get("date", "")), timezone)
    home_name = str((home.get("team") or {}).get("displayName", "") or "")
    away_name = str((away.get("team") or {}).get("displayName", "") or "")
    home_score = home.get("score")
    away_score = away.get("score")
    status_block = (competition.get("status") or {}).get("type") or {}
    status_state = status_block.get("state", "")
    completed = bool(status_block.get("completed"))
    normalized_status = _normalize_match_status(
        completed=completed,
        candidates=[
            status_state,
            status_block.get("name"),
            status_block.get("shortDetail"),
            status_block.get("detail"),
            status_block.get("description"),
        ],
    )
    home_goals = _parse_score(home_score)
    away_goals = _parse_score(away_score)

    return {
        "EventId": str(event.get("id", "")),
        "ExternalId": str(event.get("id", "")),
        "KickoffAt": event_date,
        "Date": event_date.strftime("%d/%m/%Y"),
        "MatchDate": event_date.date(),
        "Time": event_date.strftime("%H:%M"),
        "HomeTeamRaw": home_name,
        "AwayTeamRaw": away_name,
        "HomeTeam": home_name,
        "AwayTeam": away_name,
        "Status": normalized_status,
        "StatusDetail": _normalize_status_token(status_state),
        "FTHG": home_goals,
        "FTAG": away_goals,
        "HC": _extract_team_stat(home, ["wonCorners", "CW"]),
        "AC": _extract_team_stat(away, ["wonCorners", "CW"]),
        "HS": _extract_team_stat(home, ["totalShots", "SH"]),
        "AS": _extract_team_stat(away, ["totalShots", "SH"]),
        "HST": _extract_team_stat(home, ["shotsOnTarget", "ST"]),
        "AST": _extract_team_stat(away, ["shotsOnTarget", "ST"]),
        "FixtureLabel": f"{event_date.strftime('%d/%m/%Y %H:%M')} | {home_name} vs {away_name}",
        "Source": source,
    }


def extract_moneyline_odds(summary: dict[str, Any]) -> list[dict[str, Any]]:
    odds_data = _extract_primary_odds(summary)
    if not odds_data:
        return []

    provider = ((odds_data.get("provider") or {}).get("name")) or "ESPN"
    captured_at = _parse_captured_at(odds_data.get("timestamp")) or utc_now()
    selections = [
        ("HOME", ((odds_data.get("homeTeamOdds") or {}).get("moneyLine"))),
        ("DRAW", ((odds_data.get("drawOdds") or {}).get("moneyLine"))),
        ("AWAY", ((odds_data.get("awayTeamOdds") or {}).get("moneyLine"))),
    ]

    snapshots: list[dict[str, Any]] = []
    for selection, american_price in selections:
        decimal_odds = _american_to_decimal(american_price)
        if decimal_odds is None:
            continue
        snapshots.append(
            {
                "market": "1X2",
                "selection": selection,
                "decimal_odds": decimal_odds,
                "sportsbook": provider,
                "captured_at": captured_at,
            }
        )
    return snapshots


def _normalize_market_text(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _extract_pickcenter_outcomes(entry: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("outcomes", "selections", "offers", "items"):
        outcomes = entry.get(key)
        if isinstance(outcomes, list):
            return [item for item in outcomes if isinstance(item, dict)]
    return []


def _classify_pickcenter_market(entry: dict[str, Any]) -> tuple[str, str] | None:
    market_tokens = " ".join(
        [
            _normalize_market_text(entry.get("name")),
            _normalize_market_text(entry.get("text")),
            _normalize_market_text(entry.get("displayName")),
            _normalize_market_text(entry.get("description")),
            _normalize_market_text(entry.get("details")),
            _normalize_market_text(entry.get("marketType")),
        ]
    )
    if any(token in market_tokens for token in ("both teams to score", "btts", "ambos marcan")):
        return "BTTS", ""
    if ("over" in market_tokens or "under" in market_tokens or "total" in market_tokens) and "2.5" in market_tokens:
        return "TOTAL_GOALS", "2_5"
    return None


def _classify_pickcenter_selection(market_name: str, market_detail: str, outcome: dict[str, Any]) -> str | None:
    selection_tokens = " ".join(
        [
            _normalize_market_text(outcome.get("name")),
            _normalize_market_text(outcome.get("label")),
            _normalize_market_text(outcome.get("text")),
            _normalize_market_text(outcome.get("description")),
            _normalize_market_text(outcome.get("details")),
        ]
    )
    if market_name == "BTTS":
        if any(token in selection_tokens for token in ("yes", "si", "sí")):
            return "YES"
        if "no" in selection_tokens:
            return "NO"
        return None
    if market_name == "TOTAL_GOALS" and market_detail == "2_5":
        if "over" in selection_tokens:
            return "OVER_2_5"
        if "under" in selection_tokens:
            return "UNDER_2_5"
    return None


def extract_supported_odds(summary: dict[str, Any]) -> list[dict[str, Any]]:
    primary_odds = _extract_primary_odds(summary)
    default_provider = ((primary_odds.get("provider") or {}).get("name")) or "ESPN"
    default_captured_at = _parse_captured_at(primary_odds.get("timestamp")) or utc_now()

    snapshots: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for snapshot in extract_moneyline_odds(summary):
        key = (str(snapshot["market"]), str(snapshot["selection"]))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        snapshots.append(snapshot)

    for entry in summary.get("pickcenter") or []:
        if not isinstance(entry, dict):
            continue
        classified_market = _classify_pickcenter_market(entry)
        if classified_market is None:
            continue
        market_name, market_detail = classified_market
        provider = ((entry.get("provider") or {}).get("name")) or default_provider
        captured_at = _parse_captured_at(entry.get("timestamp")) or default_captured_at
        for outcome in _extract_pickcenter_outcomes(entry):
            selection = _classify_pickcenter_selection(market_name, market_detail, outcome)
            if selection is None:
                continue
            decimal_odds = _to_decimal_odds(
                outcome.get("price")
                or outcome.get("odds")
                or outcome.get("decimalOdds")
                or outcome.get("moneyLine")
                or outcome.get("americanOdds")
            )
            if decimal_odds is None:
                continue
            key = (market_name, selection)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            snapshots.append(
                {
                    "market": market_name,
                    "selection": selection,
                    "decimal_odds": decimal_odds,
                    "sportsbook": provider,
                    "captured_at": captured_at,
                }
            )
    return snapshots


def season_date_range(season_type: str, *, today: date | None = None) -> tuple[str, str]:
    current_day = today or utc_today()
    if season_type == "european":
        season_start_year = current_day.year if current_day.month >= 7 else current_day.year - 1
        start_day = date(season_start_year, 7, 1)
        end_day = date(season_start_year + 1, 6, 30)
    elif season_type == "australia":
        season_start_year = current_day.year if current_day.month >= 7 else current_day.year - 1
        start_day = date(season_start_year, 7, 1)
        end_day = date(season_start_year + 1, 5, 31)
    else:
        start_day = date(current_day.year, 1, 1)
        end_day = date(current_day.year, 12, 31)
    return start_day.strftime("%Y%m%d"), end_day.strftime("%Y%m%d")


def request_espn_scoreboard(
    league_id: str,
    params: dict[str, Any],
    *,
    timeout: int = 25,
) -> dict[str, Any]:
    if not league_id:
        raise ESPNRequestError("league_id is required for ESPN scoreboard requests")
    url = f"{ESPN_BASE_URL}/{league_id}/scoreboard"
    return _request_json(url, params=params, timeout=timeout)


def request_espn_summary(
    league_id: str,
    event_id: str,
    *,
    timeout: int = 20,
) -> dict[str, Any]:
    if not league_id:
        raise ESPNRequestError("league_id is required for ESPN summary requests")
    if not event_id:
        raise ESPNRequestError("event_id is required for ESPN summary requests")
    url = f"{ESPN_BASE_URL}/{league_id}/summary"
    return _request_json(url, params={"event": event_id}, timeout=timeout)


def fetch_espn_matches_for_date(
    league_id: str,
    target_date: date,
    *,
    source: str = "ESPN",
    timeout: int = 20,
    timezone: tzinfo = DEFAULT_TIMEZONE,
) -> list[dict[str, Any]]:
    payload = request_espn_scoreboard(
        league_id,
        {"dates": target_date.strftime("%Y%m%d"), "limit": 100},
        timeout=timeout,
    )
    rows: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        row = parse_scoreboard_event(event, source=source, timezone=timezone)
        if row is not None:
            rows.append(row)
    return rows


def fetch_espn_matches_for_season(
    league_id: str,
    season_type: str,
    *,
    source: str = "HISTORY",
    timeout: int = 25,
    timezone: tzinfo = DEFAULT_TIMEZONE,
    today: date | None = None,
) -> list[dict[str, Any]]:
    start_date, end_date = season_date_range(season_type, today=today)
    payload = request_espn_scoreboard(
        league_id,
        {"dates": f"{start_date}-{end_date}", "limit": 1000},
        timeout=timeout,
    )
    rows: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        row = parse_scoreboard_event(event, source=source, timezone=timezone)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda item: (item["MatchDate"], item["Time"], item["HomeTeam"], item["AwayTeam"]))
    return rows


def fetch_espn_scoreboard(league_id: str, params: dict[str, Any], timeout: int = 25) -> dict[str, Any]:
    try:
        return request_espn_scoreboard(league_id, params, timeout=timeout)
    except ESPNProviderError as exc:
        LOGGER.warning("fetch_espn_scoreboard failed league_id=%s params=%s error=%s", league_id, params, exc)
        return {}


def fetch_espn_summary(league_id: str, event_id: str, timeout: int = 20) -> dict[str, Any]:
    try:
        return request_espn_summary(league_id, event_id, timeout=timeout)
    except ESPNProviderError as exc:
        LOGGER.warning("fetch_espn_summary failed league_id=%s event_id=%s error=%s", league_id, event_id, exc)
        return {}
