from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_health_service, get_roi_service, require_authenticated_request
from backend.app.main import app
from backend.app.services.get_health import HealthCheck, HealthMetrics, HealthSnapshot
from backend.app.services.roi_service import ROIGroupResult, ROIResult


app.dependency_overrides[require_authenticated_request] = lambda: None
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


def test_get_health_endpoint_returns_observability_payload() -> None:
    class StubHealthService:
        def get(self) -> HealthSnapshot:
            now = datetime(2026, 4, 18, 10, 30, tzinfo=timezone.utc)
            return HealthSnapshot(
                status="ok",
                checks={"database": HealthCheck(status="ok", ok=True)},
                last_ingestion_at=now,
                last_analysis_at=now,
                metrics=HealthMetrics(
                    database_latency_ms=12.5,
                    matches_total=15,
                    odds_total=40,
                    analyses_total=12,
                ),
            )

    app.dependency_overrides[get_health_service] = lambda: StubHealthService()
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_health_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"]["ok"] is True
    assert payload["last_ingestion_at"] == "2026-04-18T10:30:00Z"
    assert payload["last_analysis_at"] == "2026-04-18T10:30:00Z"
    assert payload["metrics"]["database_latency_ms"] == 12.5
    assert payload["metrics"]["matches_total"] == 15
    assert payload["metrics"]["odds_total"] == 40
    assert payload["metrics"]["analyses_total"] == 12


def test_get_health_endpoint_returns_503_when_database_check_fails() -> None:
    class StubHealthService:
        def get(self) -> HealthSnapshot:
            return HealthSnapshot(
                status="degraded",
                checks={"database": HealthCheck(status="error", ok=False, detail="db unavailable")},
                last_ingestion_at=None,
                last_analysis_at=None,
                metrics=HealthMetrics(
                    database_latency_ms=250.0,
                    matches_total=0,
                    odds_total=0,
                    analyses_total=0,
                ),
            )

    app.dependency_overrides[get_health_service] = lambda: StubHealthService()
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_health_service, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"]["ok"] is False
    assert payload["checks"]["database"]["detail"] == "db unavailable"


def test_get_performance_summary_endpoint_returns_metrics() -> None:
    class StubROIService:
        def calculate(self, _query) -> ROIResult:
            return ROIResult(
                total_bets=8,
                total_stake=20.0,
                total_profit=4.0,
                roi=0.2,
                wins=4,
                losses=3,
                pushes=1,
            )

        def group_by_league(self, _query):
            return []

        def group_by_market(self, _query):
            return []

    app.dependency_overrides[get_roi_service] = lambda: StubROIService()
    try:
        response = client.get("/performance/summary?start_date=2026-04-01&end_date=2026-04-18")
    finally:
        app.dependency_overrides.pop(get_roi_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_bets"] == 8
    assert payload["summary"]["total_stake"] == 20.0
    assert payload["summary"]["total_profit"] == 4.0
    assert payload["summary"]["roi"] == 0.2
    assert payload["summary"]["wins"] == 4


def test_get_performance_breakdowns_handle_empty_data() -> None:
    class StubROIService:
        def calculate(self, _query) -> ROIResult:
            return ROIResult(
                total_bets=0,
                total_stake=0.0,
                total_profit=0.0,
                roi=None,
                wins=0,
                losses=0,
                pushes=0,
            )

        def group_by_league(self, _query) -> list[ROIGroupResult]:
            return []

        def group_by_market(self, _query) -> list[ROIGroupResult]:
            return []

    app.dependency_overrides[get_roi_service] = lambda: StubROIService()
    try:
        by_league_response = client.get("/performance/by-league?start_date=2026-04-01&end_date=2026-04-18")
        by_market_response = client.get("/performance/by-market?start_date=2026-04-01&end_date=2026-04-18")
    finally:
        app.dependency_overrides.pop(get_roi_service, None)

    assert by_league_response.status_code == 200
    assert by_league_response.json() == {"items": []}
    assert by_market_response.status_code == 200
    assert by_market_response.json() == {"items": []}


def test_get_performance_breakdowns_return_grouped_metrics() -> None:
    class StubROIService:
        def calculate(self, _query) -> ROIResult:
            return ROIResult(
                total_bets=0,
                total_stake=0.0,
                total_profit=0.0,
                roi=None,
                wins=0,
                losses=0,
                pushes=0,
            )

        def group_by_league(self, _query) -> list[ROIGroupResult]:
            return [
                ROIGroupResult(
                    key="LaLiga",
                    metrics=ROIResult(
                        total_bets=3,
                        total_stake=9.0,
                        total_profit=1.8,
                        roi=0.2,
                        wins=2,
                        losses=1,
                        pushes=0,
                    ),
                )
            ]

        def group_by_market(self, _query) -> list[ROIGroupResult]:
            return [
                ROIGroupResult(
                    key="1X2",
                    metrics=ROIResult(
                        total_bets=5,
                        total_stake=12.0,
                        total_profit=3.0,
                        roi=0.25,
                        wins=3,
                        losses=2,
                        pushes=0,
                    ),
                )
            ]

    app.dependency_overrides[get_roi_service] = lambda: StubROIService()
    try:
        by_league_response = client.get("/performance/by-league?start_date=2026-04-01&end_date=2026-04-18")
        by_market_response = client.get("/performance/by-market?start_date=2026-04-01&end_date=2026-04-18")
    finally:
        app.dependency_overrides.pop(get_roi_service, None)

    assert by_league_response.status_code == 200
    assert by_league_response.json()["items"][0]["key"] == "LaLiga"
    assert by_league_response.json()["items"][0]["metrics"]["roi"] == 0.2
    assert by_market_response.status_code == 200
    assert by_market_response.json()["items"][0]["key"] == "1X2"
    assert by_market_response.json()["items"][0]["metrics"]["total_profit"] == 3.0
