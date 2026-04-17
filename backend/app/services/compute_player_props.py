from __future__ import annotations

from backend.app.domain.player_props import build_player_probabilities


class ComputePlayerPropsService:
    def compute(self, payload: dict) -> dict:
        return build_player_probabilities(payload)
