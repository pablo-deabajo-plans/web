"""External provider clients."""

from backend.app.repositories.providers.bzzoiro import (
    fetch_bzzoiro_events_for_date,
    fetch_bzzoiro_odds_comparison,
    find_bzzoiro_event,
    parse_bzzoiro_comparison_odds,
)
from backend.app.repositories.providers.espn import (
    fetch_espn_matches_for_date,
    fetch_espn_matches_for_season,
    fetch_espn_scoreboard,
    fetch_espn_summary,
)
from backend.app.repositories.providers.sportmonks import fetch_sportmonks_paginated, fetch_sportmonks_resource

__all__ = [
    "fetch_bzzoiro_events_for_date",
    "fetch_bzzoiro_odds_comparison",
    "find_bzzoiro_event",
    "parse_bzzoiro_comparison_odds",
    "fetch_espn_matches_for_date",
    "fetch_espn_matches_for_season",
    "fetch_espn_scoreboard",
    "fetch_espn_summary",
    "fetch_sportmonks_paginated",
    "fetch_sportmonks_resource",
]
