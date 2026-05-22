from pathlib import Path


SCHEMA_SQL = Path("backend/app/repositories/postgres/schema.sql")
DOMAIN_SCHEMAS_SQL = Path("backend/app/repositories/postgres/domain_schemas.sql")
MATCH_REPOSITORY = Path("backend/app/repositories/postgres/matches.py")
ODDS_REPOSITORY = Path("backend/app/repositories/postgres/odds.py")
ANALYSIS_WORKER = Path("backend/workers/analysis_worker.py")


def test_runtime_schema_bootstrap_is_not_destructive() -> None:
    schema = SCHEMA_SQL.read_text(encoding="utf-8").lower()

    assert "drop column" not in schema
    assert "drop constraint" not in schema
    assert "update " not in schema


def test_runtime_schema_bootstrap_does_not_grant_plans_by_email() -> None:
    schema = SCHEMA_SQL.read_text(encoding="utf-8").lower()

    assert "gmail =" not in schema
    assert "plan = 'pro'" not in schema


def test_domain_schemas_define_separate_data_boundaries() -> None:
    schema = DOMAIN_SCHEMAS_SQL.read_text(encoding="utf-8").lower()

    assert "create schema if not exists app" in schema
    assert "create schema if not exists sports" in schema
    assert "create schema if not exists model" in schema
    assert "create table if not exists app.users" in schema
    assert "create table if not exists sports.matches" in schema
    assert "create table if not exists sports.odds_snapshots" in schema
    assert "create table if not exists model.predictions" in schema
    assert "create table if not exists model.prediction_results" in schema


def test_ingestion_dual_writes_to_sports_and_model_schemas() -> None:
    matches_repository = MATCH_REPOSITORY.read_text(encoding="utf-8").lower()
    odds_repository = ODDS_REPOSITORY.read_text(encoding="utf-8").lower()
    analysis_worker = ANALYSIS_WORKER.read_text(encoding="utf-8").lower()

    assert "insert into sports.matches" in matches_repository
    assert "insert into sports.team_match_stats" in matches_repository
    assert "insert into sports.odds_snapshots" in odds_repository
    assert "insert into model.predictions" in analysis_worker
