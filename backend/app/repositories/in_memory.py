from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import time
from typing import Sequence

from backend.app.core.time import ensure_utc_datetime
from backend.app.domain.models import Match, OddsQuote, Pick, PlayerProp, Result, User
from backend.app.domain.pricing import build_pick
from backend.app.repositories.contracts import AuditLogRepository, LoginAttemptRepository, MatchRepository, OddsRepository, PickRepository, ResultRepository, UserRepository


class InMemoryMatchRepository(MatchRepository):
    def __init__(self, matches: list[Match] | None = None) -> None:
        self._matches = {match.id: match for match in (matches or self._seed())}

    def list_matches_for_day(self, target_date: date) -> list[Match]:
        return [match for match in self._matches.values() if ensure_utc_datetime(match.kickoff_at).date() == target_date]

    def list_finished_matches(
        self,
        competition: str,
        before_date: date,
        teams: Sequence[str] | None = None,
    ) -> list[Match]:
        selected_teams = set(teams or [])
        matches: list[Match] = []
        for match in self._matches.values():
            if match.competition != competition:
                continue
            if ensure_utc_datetime(match.kickoff_at).date() >= before_date:
                continue
            if str(match.status or "").strip().lower() != "finished":
                continue
            if match.home_score is None or match.away_score is None:
                continue
            if selected_teams and match.home_team not in selected_teams and match.away_team not in selected_teams:
                continue
            matches.append(match)
        matches.sort(key=lambda item: item.kickoff_at, reverse=True)
        return matches

    def get_match(self, match_id: str) -> Match | None:
        return self._matches.get(match_id)

    def upsert_matches(self, matches: list[Match]) -> None:
        for match in matches:
            self._matches[match.id] = match

    @staticmethod
    def _seed() -> list[Match]:
        now = datetime.now(timezone.utc)
        return [
            Match(id="match-001", external_id="match-001", competition="LaLiga", kickoff_at=now, home_team="Alpha FC", away_team="Beta FC", source="seed"),
            Match(id="match-002", external_id="match-002", competition="Premier League", kickoff_at=now, home_team="Gamma FC", away_team="Delta FC", source="seed"),
        ]


class InMemoryOddsRepository(OddsRepository):
    def __init__(self, quotes: list[OddsQuote] | None = None) -> None:
        self._quotes = quotes or self._seed()

    def list_latest_odds_for_day(self, target_date: date) -> list[OddsQuote]:
        return [
            quote
            for quote in self._quotes
            if quote.captured_at is not None and ensure_utc_datetime(quote.captured_at).date() == target_date
        ]

    def list_odds_for_match(self, match_id: str) -> list[OddsQuote]:
        return [quote for quote in self._quotes if quote.match_id == match_id]

    def upsert_odds(self, quotes: list[OddsQuote]) -> None:
        by_id = {quote.id: quote for quote in self._quotes if quote.id is not None}
        for quote in quotes:
            if quote.id is not None:
                by_id[quote.id] = quote
            else:
                self._quotes.append(quote)
        self._quotes = list(by_id.values()) + [quote for quote in self._quotes if quote.id is None]

    @staticmethod
    def _seed() -> list[OddsQuote]:
        now = datetime.now(timezone.utc)
        return [
            OddsQuote(id="odds-001", match_id="match-001", market="1X2", selection="HOME", decimal_odds=2.10, sportsbook="seed", captured_at=now),
            OddsQuote(id="odds-002", match_id="match-002", market="1X2", selection="AWAY", decimal_odds=1.90, sportsbook="seed", captured_at=now),
        ]


class InMemoryPickRepository(PickRepository):
    def __init__(self, picks: list[Pick] | None = None, player_props: list[PlayerProp] | None = None) -> None:
        self._picks = {pick.id: pick for pick in (picks or self._seed())}
        self._player_props = list(player_props or [])

    def list_picks_for_day(self, target_date: date) -> list[Pick]:
        return [
            pick
            for pick in self._picks.values()
            if pick.created_at is not None and ensure_utc_datetime(pick.created_at).date() == target_date
        ]

    def list_picks_for_match(self, match_id: str) -> list[Pick]:
        return [pick for pick in self._picks.values() if pick.match_id == match_id]

    def get_pick(self, pick_id: str) -> Pick | None:
        return self._picks.get(pick_id)

    def save_pick(self, pick: Pick) -> None:
        self._picks[pick.id] = pick

    def save_player_props(self, props: list[PlayerProp]) -> None:
        self._player_props.extend(props)

    @staticmethod
    def _seed() -> list[Pick]:
        now = datetime.now(timezone.utc)
        return [
            build_pick(match_id="match-001", market="1X2", selection="HOME", probability=0.56, offered_odds=2.10, provider="seed", pick_id="pick-match-001-1x2-home", created_at=now),
            build_pick(match_id="match-002", market="1X2", selection="AWAY", probability=0.48, offered_odds=1.90, provider="seed", pick_id="pick-match-002-1x2-away", created_at=now),
        ]


class InMemoryResultRepository(ResultRepository):
    def __init__(self, results: list[Result] | None = None) -> None:
        self._results = {result.id: result for result in (results or self._seed())}

    def list_results_for_day(self, target_date: date) -> list[Result]:
        return [
            result
            for result in self._results.values()
            if result.settled_at is not None and ensure_utc_datetime(result.settled_at).date() == target_date
        ]

    def list_results_for_pick(self, pick_id: str) -> list[Result]:
        return [result for result in self._results.values() if result.pick_id == pick_id]

    def settle_pick(self, pick_id: str, stake_units: float, profit_units: float, status: str) -> Result:
        settled = datetime.now(timezone.utc)
        existing = next((result for result in self._results.values() if result.pick_id == pick_id), None)
        if existing is not None:
            updated = replace(existing, status=status, stake_units=stake_units, profit_units=profit_units, settled_at=settled)
            self._results[updated.id] = updated
            return updated
        result = Result(
            id=f"result-{len(self._results) + 1:03d}",
            pick_id=pick_id,
            status=status,
            stake_units=stake_units,
            profit_units=profit_units,
            settled_selection=None,
            settled_at=settled,
        )
        self._results[result.id] = result
        return result

    @staticmethod
    def _seed() -> list[Result]:
        now = datetime.now(timezone.utc)
        return [
            Result(
                id="result-001",
                pick_id="pick-match-001-1x2-home",
                status="won",
                stake_units=5.0,
                profit_units=5.5,
                settled_selection="home",
                settled_at=now,
            )
        ]


class InMemoryAuditLogRepository(AuditLogRepository):
    def log(self, user_id: str | None, action: str, metadata: dict) -> None:
        pass  # no-op for in-memory / test environments


class InMemoryLoginAttemptRepository(LoginAttemptRepository):
    def __init__(self) -> None:
        self._data: dict[str, list[float]] = {}

    def get_recent_failures(self, key: str, window_seconds: int) -> int:
        cutoff = time.time() - window_seconds
        recent = [ts for ts in self._data.get(key, []) if ts >= cutoff]
        self._data[key] = recent
        return len(recent)

    def record_failure(self, key: str) -> None:
        self._data.setdefault(key, []).append(time.time())

    def clear_failures(self, key: str) -> None:
        self._data.pop(key, None)


class InMemoryUserRepository(UserRepository):
    def __init__(self, users: list[User] | None = None) -> None:
        self._users = {user.id: user for user in (users or [])}
        self._verification_tokens: dict[str, tuple[str, datetime]] = {}  # token → (user_id, expires_at)
        self._reset_tokens: dict[str, tuple[str, datetime]] = {}  # token → (user_id, expires_at)

    def get_by_id(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def get_by_gmail(self, gmail: str) -> User | None:
        normalized = str(gmail or "").strip().lower()
        return next((user for user in self._users.values() if user.gmail.lower() == normalized), None)

    def create_user(self, user: User) -> None:
        if self.get_by_gmail(user.gmail) is not None:
            raise ValueError("gmail already exists")
        self._users[user.id] = user

    def update_nombre(self, user_id: str, nombre: str) -> User:
        user = self._users[user_id]
        updated = replace(user, nombre=nombre)
        self._users[user_id] = updated
        return updated

    def update_password_hash(self, user_id: str, password_hash: str) -> User:
        user = self._users[user_id]
        updated = replace(user, password_hash=password_hash)
        self._users[user_id] = updated
        return updated

    def update_password_changed_at(self, user_id: str) -> None:
        user = self._users[user_id]
        updated = replace(user, password_changed_at=datetime.now(timezone.utc))
        self._users[user_id] = updated

    def create_verification_token(self, user_id: str, token: str, expires_at: datetime) -> None:
        for existing_token, (uid, _) in list(self._verification_tokens.items()):
            if uid == user_id:
                del self._verification_tokens[existing_token]
        self._verification_tokens[token] = (user_id, expires_at)

    def get_by_verification_token(self, token: str) -> User | None:
        entry = self._verification_tokens.get(token)
        if entry is None:
            return None
        user_id, expires_at = entry
        if datetime.now(timezone.utc) > expires_at:
            return None
        return self._users.get(user_id)

    def verify_email(self, user_id: str, verified_at: datetime) -> User:
        user = self._users[user_id]
        updated = replace(user, email_verified_at=verified_at)
        self._users[user_id] = updated
        for token, (uid, _) in list(self._verification_tokens.items()):
            if uid == user_id:
                del self._verification_tokens[token]
        return updated

    def create_session(self, session_id: str, user_id: str, csrf_token: str, expires_at: datetime) -> None:
        pass

    def session_exists(self, session_id: str) -> bool:
        return True

    def delete_session(self, session_id: str) -> None:
        pass

    def create_reset_token(self, user_id: str, token: str, expires_at: datetime) -> None:
        for existing_token, (uid, _) in list(self._reset_tokens.items()):
            if uid == user_id:
                del self._reset_tokens[existing_token]
        self._reset_tokens[token] = (user_id, expires_at)

    def get_by_reset_token(self, token: str) -> User | None:
        entry = self._reset_tokens.get(token)
        if entry is None:
            return None
        user_id, expires_at = entry
        if datetime.now(timezone.utc) > expires_at:
            return None
        return self._users.get(user_id)

    def delete_reset_token(self, user_id: str) -> None:
        for token, (uid, _) in list(self._reset_tokens.items()):
            if uid == user_id:
                del self._reset_tokens[token]
