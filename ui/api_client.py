from __future__ import annotations

import os
from datetime import date
from typing import Any

import requests
import streamlit as st


DEFAULT_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_API_KEY = os.getenv("API_AUTH_KEY", "").strip()


class BackendApiError(RuntimeError):
    pass


def _headers(*, sportmonks_token: str = "") -> dict[str, str]:
    headers: dict[str, str] = {}
    if DEFAULT_API_KEY:
        headers["X-API-Key"] = DEFAULT_API_KEY
    token = str(sportmonks_token or "").strip()
    if token:
        headers["X-Sportmonks-Token"] = token
    return headers


def _request(method: str, path: str, *, params: dict[str, Any] | None = None, json_payload: Any = None, sportmonks_token: str = "") -> Any:
    response = requests.request(
        method,
        f"{DEFAULT_API_URL}{path}",
        params=params,
        json=json_payload,
        headers=_headers(sportmonks_token=sportmonks_token),
        timeout=30,
    )
    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("detail", response.text)
        except ValueError:
            detail = response.text
        raise BackendApiError(f"{method} {path} failed: {response.status_code} {detail}")
    return response.json()


@st.cache_data(ttl=300, show_spinner=False)
def get_leagues(day: date, competition_view: str) -> list[dict]:
    return _request("GET", "/dashboard/leagues", params={"day": day.isoformat(), "competition_view": competition_view})


@st.cache_data(ttl=60, show_spinner=False)
def search_matches(day: date, query: str) -> list[dict]:
    return _request("GET", "/dashboard/search", params={"day": day.isoformat(), "query": query})


@st.cache_data(ttl=120, show_spinner=False)
def get_league_dashboard(league: str, day: date) -> dict:
    return _request("GET", f"/dashboard/league/{league}", params={"day": day.isoformat()})


@st.cache_data(ttl=120, show_spinner=False)
def get_daily_value_ranking(day: date, competition_view: str) -> list[dict]:
    return _request("GET", "/dashboard/daily-value-ranking", params={"day": day.isoformat(), "competition_view": competition_view})


@st.cache_data(ttl=120, show_spinner=False)
def get_match_dashboard(league: str, day: date, match_id: str, sportmonks_token: str = "") -> dict:
    return _request(
        "GET",
        f"/dashboard/match/{match_id}",
        params={"day": day.isoformat(), "league": league},
        sportmonks_token=sportmonks_token,
    )


def compare_odds(rows: list[dict]) -> list[dict]:
    return _request("POST", "/dashboard/compare-odds", json_payload={"rows": rows})


def calculate_kelly(*, market: str, probability: float, offered_odds: float, bankroll: float, mode: str) -> dict:
    return _request(
        "POST",
        "/dashboard/kelly",
        json_payload={
            "market": market,
            "probability": probability,
            "offered_odds": offered_odds,
            "bankroll": bankroll,
            "mode": mode,
        },
    )


def get_favorites() -> dict:
    return _request("GET", "/favorites")


def create_favorite(payload: dict) -> dict:
    return _request("POST", "/favorites", json_payload=payload)


def delete_favorite(favorite_id: str) -> dict:
    return _request("DELETE", f"/favorites/{favorite_id}")


def clear_favorites() -> dict:
    return _request("DELETE", "/favorites")
