from datetime import date

from backend.app.repositories.in_memory import InMemoryMatchRepository, InMemoryPickRepository
from backend.app.web.presenters import MATCH_TABS, build_projection_distribution, pick_label
from backend.app.web.plans import FREE_PROJECTION_MAX_ROWS_PER_SCOPE, access_for_user
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
    assert laliga_group["picks"][0]["pick_label"] == "1X2 · Victoria Alpha FC"


def test_pick_label_describes_exact_selection() -> None:
    assert pick_label("1X2", "AWAY", "AS Monaco vs Lens") == "1X2 · Victoria Lens"
    assert pick_label("BTTS", "YES") == "BTTS · Sí"
    assert pick_label("TOTAL_GOALS", "OVER_2_5") == "TOTAL_GOALS · Over 2.5"


def test_match_tabs_keep_required_product_order() -> None:
    assert MATCH_TABS == (
        ("summary", "Resumen ejecutivo"),
        ("projection", "Proyección del partido"),
        ("odds", "Cuotas y valor"),
        ("season", "Estadísticas de temporada"),
        ("compare", "Comparativa & H2H"),
        ("players", "Jugadores"),
    )


def test_projection_distribution_builds_supported_thresholds() -> None:
    analysis = {
        "xg_local": 1.4,
        "xg_visitante": 0.9,
        "resultado": {
            "total_corners": 9.2,
            "home_corners": 5.1,
            "away_corners": 4.1,
            "home_shots": 13.0,
            "away_shots": 9.0,
            "home_shots_on_target": 5.0,
            "away_shots_on_target": 3.0,
            "total_cards": 4.3,
        },
        "stats_local": {"home": {"has_corners": True, "has_shots": True, "has_shots_on_target": True, "has_cards": True}},
        "stats_visitante": {"away": {"has_corners": True, "has_shots": True, "has_shots_on_target": True, "has_cards": True}},
    }

    distribution = build_projection_distribution(analysis, "corners", 0.30)

    assert distribution["has_rows"] is True
    assert [scope["key"] for scope in distribution["scopes"]] == ["total", "home", "away"]
    total_rows = distribution["scopes"][0]["rows"]
    assert total_rows
    assert all(row["probability"] >= 0.30 for row in total_rows)
    assert total_rows == sorted(total_rows, key=lambda item: item["probability"], reverse=True)


def test_projection_distribution_does_not_force_unsupported_fouls() -> None:
    analysis = {
        "xg_local": 1.4,
        "xg_visitante": 0.9,
        "resultado": {},
        "stats_local": {"home": {}},
        "stats_visitante": {"away": {}},
    }

    distribution = build_projection_distribution(analysis, "fouls", 0.30)

    assert distribution["has_rows"] is False
    assert distribution["scopes"][0]["message"] == "Datos insuficientes"


def test_free_plan_limits_leagues_tabs_and_projection_distribution() -> None:
    access = access_for_user(None)
    rows = [
        {"league": "LaLiga"},
        {"league": "Premier League"},
        {"league": "Champions League"},
        {"league": "MLS"},
    ]

    assert [row["league"] for row in access.filter_league_rows(rows)] == ["LaLiga", "Premier League"]
    assert access.can_view_daily_value is False
    assert access.can_view_odds_value is False
    assert access.coerce_match_tab("odds") == "summary"
    assert access.coerce_projection_stat("shots") == "corners"
    assert access.coerce_projection_min_probability(0.30) == 0.50

    distribution = {
        "scopes": [
            {"key": "total", "available": True, "rows": [{"threshold": str(index)} for index in range(10)]},
            {"key": "home", "available": True, "rows": [{"threshold": "home"}]},
            {"key": "away", "available": True, "rows": [{"threshold": "away"}]},
        ],
        "has_rows": True,
    }

    limited = access.filter_projection_distribution(distribution)

    assert limited["is_limited"] is True
    assert [scope["key"] for scope in limited["scopes"]] == ["total"]
    assert len(limited["scopes"][0]["rows"]) == FREE_PROJECTION_MAX_ROWS_PER_SCOPE


def test_pro_plan_keeps_full_access() -> None:
    class UserStub:
        plan = "pro"

    access = access_for_user(UserStub())  # type: ignore[arg-type]
    rows = [{"league": "Champions League"}, {"league": "MLS"}]
    distribution = {"scopes": [{"key": "home", "rows": [{"threshold": "home"}]}], "has_rows": True}

    assert access.filter_league_rows(rows) == rows
    assert access.can_view_daily_value is True
    assert access.can_view_odds_value is True
    assert access.coerce_match_tab("odds") == "odds"
    assert access.coerce_projection_stat("shots") == "shots"
    assert access.coerce_projection_min_probability(0.30) == 0.30
    assert access.filter_projection_distribution(distribution) is distribution
