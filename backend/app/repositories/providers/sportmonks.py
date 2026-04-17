from __future__ import annotations

from typing import Any

import requests

from backend.app.core.logging import get_logger


LOGGER = get_logger(__name__)
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_sportmonks_resource(base_url: str, path: str, token: str, params: dict[str, Any] | None = None, timeout: int = 25) -> dict:
    if not token:
        return {}
    query = {"api_token": token}
    if params:
        query.update({key: value for key, value in params.items() if value not in {None, ""}})
    try:
        response = requests.get(f"{base_url}{path}", params=query, headers=HTTP_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("fetch_sportmonks_resource failed path=%s params=%s error=%s", path, params or {}, exc)
        return {}


def fetch_sportmonks_paginated(base_url: str, path: str, token: str, params: dict[str, Any] | None = None, max_pages: int = 4) -> list[dict]:
    results: list[dict] = []
    page = 1
    base_params = dict(params or {})
    per_page = int(base_params.get("per_page", 50) or 50)

    while page <= max_pages:
        payload = fetch_sportmonks_resource(base_url, path, token, {**base_params, "page": page})
        data = payload.get("data") or []
        if isinstance(data, dict):
            data = [data]
        if not data:
            break
        results.extend(data)
        pagination = payload.get("pagination") or ((payload.get("meta") or {}).get("pagination")) or {}
        current_page = int(pagination.get("current_page") or page)
        last_page = int(pagination.get("last_page") or current_page)
        if current_page >= last_page or len(data) < per_page:
            break
        page += 1

    return results
