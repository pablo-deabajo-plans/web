from datetime import date

from backend.app.repositories.in_memory import InMemoryMatchRepository, InMemoryPickRepository
from backend.app.web.router import _stored_daily_value_ranking, _stored_league_dashboard


def _seed_day(match_repository: InMemoryMatchRepository) -> date:
    match = match_repository.get_match("match-001")
    assert match is not None
    return match.kickoff_at.date()


def test_stored_league_dashboard_uses_persisted_ranking() -> None:
    match_repository = InMemoryMatchRepository()
    pick_repository = InMemoryPickRepository()
    target_day = _seed_day(match_repository)

    dashboard = _stored_league_dashboard(target_day, "LaLiga", match_repository, pick_repository)

    assert dashboard["league"] == "LaLiga"
    assert dashboard["match_count"] == 1
    assert dashboard["ranking"]
    assert dashboard["ranking"][0]["market"] == "1X2"
    assert dashboard["ranking"][0]["match"] == "Alpha FC vs Beta FC"


def test_daily_value_and_league_detail_share_same_persisted_pick_source() -> None:
    match_repository = InMemoryMatchRepository()
    pick_repository = InMemoryPickRepository()
    target_day = _seed_day(match_repository)

    ranking_groups = _stored_daily_value_ranking(target_day, "Ligas", match_repository, pick_repository)
    laliga_group = next(group for group in ranking_groups if group["league"] == "LaLiga")
    league_dashboard = _stored_league_dashboard(target_day, "LaLiga", match_repository, pick_repository)

    assert laliga_group["picks"][0]["match_id"] == league_dashboard["ranking"][0]["match_id"]
    assert laliga_group["picks"][0]["market"] == league_dashboard["ranking"][0]["market"]
    assert laliga_group["picks"][0]["offered_odds"] == league_dashboard["ranking"][0]["offered_odds"]
