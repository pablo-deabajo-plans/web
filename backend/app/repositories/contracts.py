from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, Sequence

from backend.app.domain.models import Match, OddsQuote, Pick, PlayerProp, Result, User


class MatchRepository(Protocol):
    def list_matches_for_day(self, target_date: date) -> Sequence[Match]:
        ...

    def list_finished_matches(
        self,
        competition: str,
        before_date: date,
        teams: Sequence[str] | None = None,
    ) -> Sequence[Match]:
        ...

    def get_match(self, match_id: str) -> Match | None:
        ...

    def upsert_matches(self, matches: Sequence[Match]) -> None:
        ...


class OddsRepository(Protocol):
    def list_latest_odds_for_day(self, target_date: date) -> Sequence[OddsQuote]:
        ...

    def list_odds_for_match(self, match_id: str) -> Sequence[OddsQuote]:
        ...

    def upsert_odds(self, quotes: Sequence[OddsQuote]) -> None:
        ...


class PickRepository(Protocol):
    def list_picks_for_day(self, target_date: date) -> Sequence[Pick]:
        ...

    def list_picks_for_match(self, match_id: str) -> Sequence[Pick]:
        ...

    def get_pick(self, pick_id: str) -> Pick | None:
        ...

    def save_pick(self, pick: Pick) -> None:
        ...

    def save_player_props(self, props: Sequence[PlayerProp]) -> None:
        ...


class ResultRepository(Protocol):
    def list_results_for_day(self, target_date: date) -> Sequence[Result]:
        ...

    def list_results_for_pick(self, pick_id: str) -> Sequence[Result]:
        ...

    def settle_pick(self, pick_id: str, stake_units: float, profit_units: float, status: str) -> Result:
        ...


class UserRepository(Protocol):
    def get_by_id(self, user_id: str) -> User | None:
        ...

    def get_by_gmail(self, gmail: str) -> User | None:
        ...

    def create_user(self, user: User) -> None:
        ...

    def update_nombre(self, user_id: str, nombre: str) -> User:
        ...

    def update_password_hash(self, user_id: str, password_hash: str) -> User:
        ...

    def update_password_changed_at(self, user_id: str) -> None:
        ...

    def create_verification_token(self, user_id: str, token: str, expires_at: datetime) -> None:
        ...

    def get_by_verification_token(self, token: str) -> User | None:
        ...

    def verify_email(self, user_id: str, verified_at: datetime) -> User:
        ...

    def create_session(self, session_id: str, user_id: str, csrf_token: str, expires_at: datetime) -> None:
        ...

    def session_exists(self, session_id: str) -> bool:
        ...

    def delete_session(self, session_id: str) -> None:
        ...


class LoginAttemptRepository(Protocol):
    def get_recent_failures(self, key: str, window_seconds: int) -> int:
        ...

    def record_failure(self, key: str) -> None:
        ...

    def clear_failures(self, key: str) -> None:
        ...


class AuditLogRepository(Protocol):
    def log(self, user_id: str | None, action: str, metadata: dict) -> None:
        ...
