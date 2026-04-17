from __future__ import annotations

import pandas as pd

from backend.app.domain.analysis import build_insights, build_match_analysis


class AnalyzeMatchService:
    def analyze(
        self,
        df: pd.DataFrame,
        liga: str,
        local: str,
        visitante: str,
        match_date=None,
        match_label: str = "",
    ) -> dict | None:
        return build_match_analysis(
            df,
            liga,
            local,
            visitante,
            match_date=match_date,
            match_label=match_label,
        )

    def insights(self, analysis: dict) -> list[str]:
        return build_insights(analysis)
