from __future__ import annotations

from typing import Any

import requests

from backend.app.core.logging import get_logger


LOGGER = get_logger(__name__)
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_espn_scoreboard(league_id: str, params: dict[str, Any], timeout: int = 25) -> dict:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"
    try:
        response = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("fetch_espn_scoreboard failed league_id=%s params=%s error=%s", league_id, params, exc)
        return {}


def fetch_espn_summary(league_id: str, event_id: str, timeout: int = 20) -> dict:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/summary"
    try:
        response = requests.get(url, params={"event": event_id}, headers=HTTP_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("fetch_espn_summary failed league_id=%s event_id=%s error=%s", league_id, event_id, exc)
        return {}
