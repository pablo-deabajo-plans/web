CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY
);

ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS gmail TEXT;
ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS nombre TEXT;
ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free';
ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_verification_tokens_token
    ON email_verification_tokens (token);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_plan_check'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_plan_check CHECK (plan IN ('free', 'pro')) NOT VALID;
    END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_gmail_lower ON users (lower(gmail));

CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    external_id TEXT,
    competition TEXT NOT NULL,
    kickoff_at TIMESTAMPTZ NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    source TEXT,
    home_score INTEGER,
    away_score INTEGER,
    home_corners NUMERIC(10,4),
    away_corners NUMERIC(10,4),
    home_shots NUMERIC(10,4),
    away_shots NUMERIC(10,4),
    home_shots_on_target NUMERIC(10,4),
    away_shots_on_target NUMERIC(10,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matches_kickoff_at ON matches (kickoff_at);
CREATE INDEX IF NOT EXISTS idx_matches_competition_kickoff ON matches (competition, kickoff_at);
CREATE INDEX IF NOT EXISTS idx_matches_status_kickoff ON matches (status, kickoff_at);

CREATE TABLE IF NOT EXISTS odds (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    sportsbook TEXT,
    decimal_odds NUMERIC(10,4) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_odds_match_id ON odds (match_id);
CREATE INDEX IF NOT EXISTS idx_odds_match_market_selection ON odds (match_id, market, selection);
CREATE INDEX IF NOT EXISTS idx_odds_captured_at ON odds (captured_at);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    model_version TEXT NOT NULL,
    home_win_prob NUMERIC(8,6) NOT NULL,
    draw_prob NUMERIC(8,6) NOT NULL,
    away_win_prob NUMERIC(8,6) NOT NULL,
    expected_home_goals NUMERIC(8,4) NOT NULL,
    expected_away_goals NUMERIC(8,4) NOT NULL,
    trace JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_analyses_match_model_generated
    ON analyses (match_id, model_version, generated_at);

CREATE TABLE IF NOT EXISTS picks (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    analysis_id TEXT REFERENCES analyses(id) ON DELETE SET NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    probability NUMERIC(8,6) NOT NULL,
    fair_odds NUMERIC(10,4) NOT NULL,
    offered_odds NUMERIC(10,4) NOT NULL,
    edge NUMERIC(10,6) NOT NULL,
    stake_fraction NUMERIC(10,6) NOT NULL,
    stake_units NUMERIC(10,4),
    closing_odds NUMERIC(10,4),
    clv_absolute NUMERIC(10,4),
    clv_percent NUMERIC(10,6),
    provider TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_picks_match_id ON picks (match_id);
CREATE INDEX IF NOT EXISTS idx_picks_user_created_at ON picks (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_picks_status_created_at ON picks (status, created_at);
ALTER TABLE IF EXISTS picks ADD COLUMN IF NOT EXISTS closing_odds NUMERIC(10,4);
ALTER TABLE IF EXISTS picks ADD COLUMN IF NOT EXISTS clv_absolute NUMERIC(10,4);
ALTER TABLE IF EXISTS picks ADD COLUMN IF NOT EXISTS clv_percent NUMERIC(10,6);

CREATE TABLE IF NOT EXISTS results (
    id TEXT PRIMARY KEY,
    pick_id TEXT NOT NULL UNIQUE REFERENCES picks(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    settled_selection TEXT,
    stake_units NUMERIC(10,4) NOT NULL,
    profit_units NUMERIC(10,4) NOT NULL,
    roi NUMERIC(10,6) GENERATED ALWAYS AS (
        CASE
            WHEN stake_units = 0 THEN NULL
            ELSE profit_units / stake_units
        END
    ) STORED,
    settled_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_settled_at ON results (settled_at);
CREATE INDEX IF NOT EXISTS idx_results_status_settled_at ON results (status, settled_at);

CREATE TABLE IF NOT EXISTS player_props (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    analysis_id TEXT REFERENCES analyses(id) ON DELETE SET NULL,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    metric TEXT NOT NULL,
    line NUMERIC(10,4) NOT NULL,
    probability NUMERIC(8,6) NOT NULL,
    expected_value NUMERIC(10,4) NOT NULL,
    confidence_label TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_player_props_match_metric ON player_props (match_id, metric);
CREATE INDEX IF NOT EXISTS idx_player_props_generated_at ON player_props (generated_at);

CREATE TABLE IF NOT EXISTS pipeline_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    worker_name TEXT NOT NULL,
    pipeline_run_id TEXT NOT NULL,
    target_date DATE,
    metric_value BIGINT,
    json_value JSONB,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE IF EXISTS pipeline_metrics ADD COLUMN IF NOT EXISTS id BIGSERIAL;
ALTER TABLE IF EXISTS pipeline_metrics ADD COLUMN IF NOT EXISTS pipeline_run_id TEXT;
ALTER TABLE IF EXISTS pipeline_metrics ADD COLUMN IF NOT EXISTS recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_metrics_id ON pipeline_metrics (id);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_worker_recorded_at ON pipeline_metrics (worker_name, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_metric_recorded_at ON pipeline_metrics (metric_name, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_run_recorded_at ON pipeline_metrics (pipeline_run_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id TEXT PRIMARY KEY,
    model_version TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    total_matches INTEGER NOT NULL DEFAULT 0,
    analyzed_matches INTEGER NOT NULL DEFAULT 0,
    total_picks INTEGER NOT NULL DEFAULT 0,
    resolved_bets INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    pushes INTEGER NOT NULL DEFAULT 0,
    voids INTEGER NOT NULL DEFAULT 0,
    hit_rate NUMERIC(10,6),
    total_stake NUMERIC(12,4) NOT NULL DEFAULT 0,
    total_profit NUMERIC(12,4) NOT NULL DEFAULT 0,
    roi NUMERIC(12,6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_date_range ON backtest_runs (start_date, end_date);

CREATE TABLE IF NOT EXISTS backtest_run_groups (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    group_type TEXT NOT NULL,
    group_key TEXT NOT NULL,
    league TEXT,
    market TEXT,
    total_bets INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    pushes INTEGER NOT NULL DEFAULT 0,
    voids INTEGER NOT NULL DEFAULT 0,
    hit_rate NUMERIC(10,6),
    total_stake NUMERIC(12,4) NOT NULL DEFAULT 0,
    total_profit NUMERIC(12,4) NOT NULL DEFAULT 0,
    roi NUMERIC(12,6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_backtest_run_groups_unique
    ON backtest_run_groups (run_id, group_type, group_key);
CREATE INDEX IF NOT EXISTS idx_backtest_run_groups_run_id ON backtest_run_groups (run_id);

CREATE TABLE IF NOT EXISTS login_attempts (
    key TEXT PRIMARY KEY,
    timestamps JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT,
    action      TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS backtest_picks (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    analysis_id TEXT,
    competition TEXT NOT NULL,
    kickoff_at TIMESTAMPTZ NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    probability NUMERIC(8,6) NOT NULL,
    fair_odds NUMERIC(10,4) NOT NULL,
    offered_odds NUMERIC(10,4) NOT NULL,
    edge NUMERIC(10,6) NOT NULL,
    stake_units NUMERIC(10,4) NOT NULL,
    closing_odds NUMERIC(10,4),
    clv_absolute NUMERIC(10,4),
    clv_percent NUMERIC(10,6),
    provider TEXT,
    result_status TEXT NOT NULL,
    settled_selection TEXT,
    profit_units NUMERIC(10,4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_picks_run_id ON backtest_picks (run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_picks_match_id ON backtest_picks (match_id);
CREATE INDEX IF NOT EXISTS idx_backtest_picks_league_market ON backtest_picks (competition, market);
