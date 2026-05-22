CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS sports;
CREATE SCHEMA IF NOT EXISTS model;

CREATE TABLE IF NOT EXISTS app.users (
    id TEXT PRIMARY KEY,
    gmail TEXT NOT NULL,
    nombre TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT app_users_plan_check CHECK (plan IN ('free', 'pro'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_gmail_lower ON app.users (lower(gmail));

CREATE TABLE IF NOT EXISTS app.user_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_user_sessions_user_id ON app.user_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_app_user_sessions_expires_at ON app.user_sessions (expires_at);

CREATE TABLE IF NOT EXISTS app.favorite_picks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    source_pick_id TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_favorite_picks_user_created ON app.favorite_picks (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS sports.leagues (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    external_id TEXT,
    name TEXT NOT NULL,
    country TEXT,
    season TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, external_id)
);

CREATE TABLE IF NOT EXISTS sports.teams (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    external_id TEXT,
    league_id TEXT REFERENCES sports.leagues(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    country TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, external_id)
);

CREATE INDEX IF NOT EXISTS idx_sports_teams_league_id ON sports.teams (league_id);

CREATE TABLE IF NOT EXISTS sports.players (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    external_id TEXT,
    team_id TEXT REFERENCES sports.teams(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    position TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, external_id)
);

CREATE INDEX IF NOT EXISTS idx_sports_players_team_id ON sports.players (team_id);

CREATE TABLE IF NOT EXISTS sports.matches (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    external_id TEXT,
    league_id TEXT REFERENCES sports.leagues(id) ON DELETE SET NULL,
    home_team_id TEXT REFERENCES sports.teams(id) ON DELETE SET NULL,
    away_team_id TEXT REFERENCES sports.teams(id) ON DELETE SET NULL,
    competition TEXT NOT NULL,
    kickoff_at TIMESTAMPTZ NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    home_score INTEGER,
    away_score INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, external_id)
);

CREATE INDEX IF NOT EXISTS idx_sports_matches_kickoff_at ON sports.matches (kickoff_at);
CREATE INDEX IF NOT EXISTS idx_sports_matches_competition_kickoff ON sports.matches (competition, kickoff_at);
CREATE INDEX IF NOT EXISTS idx_sports_matches_status_kickoff ON sports.matches (status, kickoff_at);

CREATE TABLE IF NOT EXISTS sports.team_match_stats (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES sports.matches(id) ON DELETE CASCADE,
    team_id TEXT REFERENCES sports.teams(id) ON DELETE SET NULL,
    side TEXT NOT NULL CHECK (side IN ('home', 'away')),
    minute INTEGER,
    goals NUMERIC(10,4),
    xg NUMERIC(10,4),
    shots NUMERIC(10,4),
    shots_on_target NUMERIC(10,4),
    corners NUMERIC(10,4),
    fouls NUMERIC(10,4),
    yellow_cards NUMERIC(10,4),
    red_cards NUMERIC(10,4),
    possession NUMERIC(10,4),
    source TEXT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sports_team_match_stats_match_side ON sports.team_match_stats (match_id, side, minute);
CREATE INDEX IF NOT EXISTS idx_sports_team_match_stats_team ON sports.team_match_stats (team_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS sports.player_match_stats (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES sports.matches(id) ON DELETE CASCADE,
    player_id TEXT REFERENCES sports.players(id) ON DELETE SET NULL,
    team_id TEXT REFERENCES sports.teams(id) ON DELETE SET NULL,
    minute INTEGER,
    goals NUMERIC(10,4),
    assists NUMERIC(10,4),
    shots NUMERIC(10,4),
    shots_on_target NUMERIC(10,4),
    passes NUMERIC(10,4),
    tackles NUMERIC(10,4),
    yellow_cards NUMERIC(10,4),
    red_cards NUMERIC(10,4),
    source TEXT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sports_player_match_stats_match ON sports.player_match_stats (match_id, player_id);
CREATE INDEX IF NOT EXISTS idx_sports_player_match_stats_player ON sports.player_match_stats (player_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS sports.match_events (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES sports.matches(id) ON DELETE CASCADE,
    team_id TEXT REFERENCES sports.teams(id) ON DELETE SET NULL,
    player_id TEXT REFERENCES sports.players(id) ON DELETE SET NULL,
    minute INTEGER,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    source TEXT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sports_match_events_match_minute ON sports.match_events (match_id, minute);
CREATE INDEX IF NOT EXISTS idx_sports_match_events_type ON sports.match_events (event_type, captured_at DESC);

CREATE TABLE IF NOT EXISTS sports.odds_snapshots (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES sports.matches(id) ON DELETE CASCADE,
    bookmaker TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    decimal_odds NUMERIC(10,4) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sports_odds_snapshots_match_market ON sports.odds_snapshots (match_id, market, selection, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_sports_odds_snapshots_bookmaker ON sports.odds_snapshots (bookmaker, captured_at DESC);

CREATE TABLE IF NOT EXISTS model.feature_sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS model.match_features (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES sports.matches(id) ON DELETE CASCADE,
    feature_set_id TEXT NOT NULL REFERENCES model.feature_sets(id) ON DELETE RESTRICT,
    generated_at TIMESTAMPTZ NOT NULL,
    features JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (match_id, feature_set_id, generated_at)
);

CREATE INDEX IF NOT EXISTS idx_model_match_features_match ON model.match_features (match_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS model.predictions (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES sports.matches(id) ON DELETE CASCADE,
    feature_set_id TEXT REFERENCES model.feature_sets(id) ON DELETE SET NULL,
    model_version TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    probability NUMERIC(8,6) NOT NULL CHECK (probability >= 0 AND probability <= 1),
    fair_odds NUMERIC(10,4),
    expected_home_goals NUMERIC(8,4),
    expected_away_goals NUMERIC(8,4),
    trace JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_predictions_match_market ON model.predictions (match_id, market, selection, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_predictions_version ON model.predictions (model_version, generated_at DESC);

CREATE TABLE IF NOT EXISTS model.prediction_results (
    id TEXT PRIMARY KEY,
    prediction_id TEXT NOT NULL REFERENCES model.predictions(id) ON DELETE CASCADE,
    outcome_status TEXT NOT NULL,
    closing_odds NUMERIC(10,4),
    brier_score NUMERIC(10,6),
    log_loss NUMERIC(10,6),
    clv_absolute NUMERIC(10,4),
    clv_percent NUMERIC(10,6),
    settled_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_prediction_results_prediction ON model.prediction_results (prediction_id);
CREATE INDEX IF NOT EXISTS idx_model_prediction_results_settled ON model.prediction_results (settled_at DESC);

CREATE TABLE IF NOT EXISTS model.backtest_runs (
    id TEXT PRIMARY KEY,
    model_version TEXT NOT NULL,
    feature_set_id TEXT REFERENCES model.feature_sets(id) ON DELETE SET NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    total_predictions INTEGER NOT NULL DEFAULT 0,
    brier_score NUMERIC(10,6),
    log_loss NUMERIC(10,6),
    roi NUMERIC(12,6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_model_backtest_runs_version_created ON model.backtest_runs (model_version, created_at DESC);
