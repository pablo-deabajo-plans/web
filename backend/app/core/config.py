from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Gordon BetScanner Backend")
    environment: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    cache_ttl_daily_picks_seconds: int = int(os.getenv("CACHE_TTL_DAILY_PICKS_SECONDS", "120"))
    cache_ttl_matches_seconds: int = int(os.getenv("CACHE_TTL_MATCHES_SECONDS", "180"))
    cache_ttl_match_detail_seconds: int = int(os.getenv("CACHE_TTL_MATCH_DETAIL_SECONDS", "120"))
    cache_ttl_history_seconds: int = int(os.getenv("CACHE_TTL_HISTORY_SECONDS", "120"))
    poisson_score_max: int = int(os.getenv("POISSON_SCORE_MAX", "12"))


settings = Settings()
