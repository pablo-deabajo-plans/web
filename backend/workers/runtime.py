from __future__ import annotations

import os
from datetime import date

from backend.app.core.time import utc_today

SHARED_DATE_ENV_NAMES = ("PIPELINE_DATE", "WORKER_DATE")


def resolve_target_date(env_name: str) -> date:
    for candidate_name in (env_name, *SHARED_DATE_ENV_NAMES):
        raw_value = os.getenv(candidate_name, "").strip()
        if not raw_value:
            continue
        try:
            return date.fromisoformat(raw_value)
        except ValueError as exc:
            raise ValueError(f"{candidate_name} must use YYYY-MM-DD format") from exc
    return utc_today()
