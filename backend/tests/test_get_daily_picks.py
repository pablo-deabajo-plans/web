from datetime import datetime, timezone

from backend.app.domain.pricing import build_pick
from backend.app.repositories.in_memory import InMemoryPickRepository
from backend.app.services.get_daily_picks import GetDailyPicksService


def test_get_daily_picks_returns_only_positive_edge_sorted_desc() -> None:
    now = datetime.now(timezone.utc)
    repository = InMemoryPickRepository(
        picks=[
            build_pick(
                match_id="a",
                market="1X2",
                selection="Home",
                probability=0.55,
                offered_odds=2.10,
                created_at=now,
            ),
            build_pick(
                match_id="b",
                market="BTTS",
                selection="Yes",
                probability=0.48,
                offered_odds=1.90,
                created_at=now,
            ),
            build_pick(
                match_id="c",
                market="Over 2.5",
                selection="Over",
                probability=0.60,
                offered_odds=2.25,
                created_at=now,
            ),
        ]
    )
    service = GetDailyPicksService(repository)

    picks = service.get_for_date(target_date=now.date(), limit=10)

    assert len(picks) == 2
    assert picks[0].edge >= picks[1].edge
    assert all(item.edge > 0 for item in picks)
