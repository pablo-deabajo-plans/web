"""External provider clients."""

from backend.app.repositories.providers.espn import fetch_espn_scoreboard, fetch_espn_summary
from backend.app.repositories.providers.sportmonks import fetch_sportmonks_paginated, fetch_sportmonks_resource

__all__ = [
    "fetch_espn_scoreboard",
    "fetch_espn_summary",
    "fetch_sportmonks_paginated",
    "fetch_sportmonks_resource",
]
