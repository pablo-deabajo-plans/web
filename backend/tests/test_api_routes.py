from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_get_picks_endpoint_returns_schema_list() -> None:
    response = client.get("/picks")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert "match_id" in payload[0]
    assert "offered_odds" in payload[0]


def test_get_matches_endpoint_returns_schema_list() -> None:
    response = client.get("/matches")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert "competition" in payload[0]
    assert "home_team" in payload[0]


def test_get_match_detail_endpoint_returns_nested_payload() -> None:
    response = client.get("/match/match-001")
    assert response.status_code == 200
    payload = response.json()
    assert "match" in payload
    assert "odds" in payload
    assert "picks" in payload


def test_get_history_endpoint_returns_aggregate_fields() -> None:
    response = client.get("/history")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total_profit_units" in payload
    assert "roi" in payload
