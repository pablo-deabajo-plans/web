"""
Integration tests that run against a real PostgreSQL database.

Run with:
    POSTGRES_HOST=localhost POSTGRES_DB=gordon_test POSTGRES_USER=gordon \
    POSTGRES_PASSWORD=secret pytest backend/tests/test_integration_e2e.py -m integration -v

These tests are skipped automatically when the database env vars are not set.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.domain.models import Match, OddsQuote
from backend.app.repositories.postgres.audit_log import PostgresAuditLogRepository
from backend.app.repositories.postgres.matches import PostgresMatchRepository
from backend.app.repositories.postgres.odds import PostgresOddsRepository
from backend.app.repositories.postgres.users import PostgresUserRepository
from backend.app.services.auth import AuthService
from backend.app.repositories.postgres.login_attempts import PostgresLoginAttemptRepository

pytestmark = pytest.mark.integration


def _match(match_id: str | None = None) -> Match:
    now = datetime.now(timezone.utc)
    mid = match_id or f"match-{uuid4().hex[:8]}"
    return Match(
        id=mid,
        competition="LaLiga",
        home_team="Real Madrid",
        away_team="Barcelona",
        kickoff_at=now,
        status="scheduled",
    )


def test_match_ingestion_and_retrieval(pg_connection_factory):
    repo = PostgresMatchRepository(pg_connection_factory)
    match = _match()
    repo.upsert_matches([match])
    results = repo.list_matches_for_day(match.kickoff_at.date())
    ids = [m.id for m in results]
    assert match.id in ids


def test_odds_write_and_read(pg_connection_factory):
    match_repo = PostgresMatchRepository(pg_connection_factory)
    match = _match()
    match_repo.upsert_matches([match])

    odds_repo = PostgresOddsRepository(pg_connection_factory)
    quote = OddsQuote(
        id=f"odds-{uuid4().hex[:8]}",
        match_id=match.id,
        market="1X2",
        selection="HOME",
        decimal_odds=2.10,
        sportsbook="Betfair",
        captured_at=match.kickoff_at,
    )
    odds_repo.upsert_odds([quote])
    quotes = odds_repo.list_odds_for_match(match.id)
    assert any(q.id == quote.id for q in quotes)


def test_user_registration_and_login(pg_connection_factory):
    user_repo = PostgresUserRepository(pg_connection_factory)
    login_repo = PostgresLoginAttemptRepository(pg_connection_factory)
    auth = AuthService(user_repo, session_secret="test-secret-key", session_ttl_seconds=3600, login_attempts=login_repo)

    gmail = f"test-{uuid4().hex[:8]}@example.com"
    user = auth.register(gmail, "Test User", "Password1!", client_key="127.0.0.1")
    assert user.gmail == gmail

    authenticated = auth.authenticate(gmail, "Password1!", client_key="127.0.0.1")
    assert authenticated.id == user.id


def test_audit_log_records_entry(pg_connection_factory):
    audit_repo = PostgresAuditLogRepository(pg_connection_factory)
    user_id = f"user-{uuid4().hex[:8]}"
    audit_repo.log(user_id, "login.success", {"gmail": "test@example.com"})

    with pg_connection_factory() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT action, user_id FROM audit_log WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
    assert row is not None
    assert row[0] == "login.success"
    assert row[1] == user_id


def test_match_retrieval_returns_empty_for_unknown_id(pg_connection_factory):
    repo = PostgresMatchRepository(pg_connection_factory)
    result = repo.get_match("nonexistent-match-id-xyz")
    assert result is None
