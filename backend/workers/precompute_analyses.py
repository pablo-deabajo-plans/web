from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date

from backend.app.domain.models import Pick, PlayerProp
from backend.app.repositories.contracts import MatchRepository, PickRepository


def run_prediction_precompute(
    *,
    target_date: date,
    match_repository: MatchRepository,
    pick_repository: PickRepository,
    compute_for_match: Callable[[str], tuple[Sequence[Pick], Sequence[PlayerProp]]],
) -> int:
    persisted = 0
    for match in match_repository.list_matches_for_day(target_date):
        picks, player_props = compute_for_match(match.id)
        for pick in picks:
            pick_repository.save_pick(pick)
            persisted += 1
        pick_repository.save_player_props(player_props)
    return persisted
