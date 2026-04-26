from datetime import datetime, timezone

from backend.app.domain.models import Result
from backend.app.domain.pricing import build_pick
from backend.app.repositories.in_memory import InMemoryPickRepository, InMemoryResultRepository
from backend.app.services.get_history import GetHistoryService


def test_history_service_joins_pick_and_result_for_day() -> None:
    now = datetime.now(timezone.utc)
    pick_repository = InMemoryPickRepository(
        picks=[
            build_pick(
                match_id="match-001",
                market="1X2",
                selection="HOME",
                probability=0.56,
                offered_odds=2.10,
                provider="test",
                pick_id="pick-001",
                created_at=now,
            )
        ]
    )
    result_repository = InMemoryResultRepository(
        results=[
            Result(
                id="result-001",
                pick_id="pick-001",
                status="won",
                stake_units=5.0,
                profit_units=5.5,
                settled_at=now,
            )
        ]
    )

    service = GetHistoryService(pick_repository, result_repository)
    items = service.list_for_date(now.date())

    assert len(items) == 1
    assert items[0].pick.id == "pick-001"
    assert items[0].result.status == "won"
