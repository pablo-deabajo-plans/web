from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from backend.app.core.logging import get_logger


LOGGER = get_logger(__name__)
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
DEFAULT_TIMEZONE = ZoneInfo("Europe/Madrid")


class ESPNProviderError(RuntimeError):
    """Base exception for ESPN provider failures."""


class ESPNRequestError(ESPNProviderError):
    """Raised when the ESPN API request fails."""


class ESPNResponseError(ESPNProviderError):
    """Raised when the ESPN payload cannot be parsed safely."""


def _request_json(url: str, *, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ESPNRequestError(f"ESPN request failed for url={url} params={params}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ESPNResponseError(f"ESPN response was not valid JSON for url={url}") from exc

    if not isinstance(payload, dict):
        raise ESPNResponseError(f"ESPN response must be a JSON object for url={url}")
    return payload


def _parse_event_datetime(value: str, timezone: ZoneInfo) -> datetime:
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


def parse_scoreboard_event(
    event: dict[str, Any],
    *,
    source: str,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
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
    status = (((competition.get("status") or {}).get("type")) or {}).get("state", "")
    completed = bool((((competition.get("status") or {}).get("type")) or {}).get("completed"))

    if completed or status == "post":
        try:
            home_goals = int(home_score) if str(home_score).strip() != "" else None
        except (TypeError, ValueError):
            home_goals = None
        try:
            away_goals = int(away_score) if str(away_score).strip() != "" else None
        except (TypeError, ValueError):
            away_goals = None
    else:
        home_goals = None
        away_goals = None

    return {
        "EventId": str(event.get("id", "")),
        "Date": event_date.strftime("%d/%m/%Y"),
        "MatchDate": event_date.date(),
        "Time": event_date.strftime("%H:%M"),
        "HomeTeamRaw": home_name,
        "AwayTeamRaw": away_name,
        "HomeTeam": home_name,
        "AwayTeam": away_name,
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


def season_date_range(season_type: str, *, today: date | None = None) -> tuple[str, str]:
    current_day = today or datetime.now(DEFAULT_TIMEZONE).date()
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
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
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
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
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

