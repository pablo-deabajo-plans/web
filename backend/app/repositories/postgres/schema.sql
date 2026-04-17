CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE matches (
    id UUID PRIMARY KEY,
    external_id TEXT,
    competition TEXT NOT NULL,
    kickoff_at TIMESTAMPTZ NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_matches_kickoff_at ON matches (kickoff_at);
CREATE INDEX idx_matches_competition_kickoff ON matches (competition, kickoff_at);

CREATE TABLE odds (
    id UUID PRIMARY KEY,
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    sportsbook TEXT,
    decimal_odds NUMERIC(10,4) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_odds_match_id ON odds (match_id);
CREATE INDEX idx_odds_match_market_selection ON odds (match_id, market, selection);
CREATE INDEX idx_odds_captured_at ON odds (captured_at);

CREATE TABLE analyses (
    id UUID PRIMARY KEY,
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
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

CREATE UNIQUE INDEX idx_analyses_match_model_generated
    ON analyses (match_id, model_version, generated_at);

CREATE TABLE picks (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id) ON DELETE SET NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    probability NUMERIC(8,6) NOT NULL,
    fair_odds NUMERIC(10,4) NOT NULL,
    offered_odds NUMERIC(10,4) NOT NULL,
    edge NUMERIC(10,6) NOT NULL,
    stake_fraction NUMERIC(10,6) NOT NULL,
    stake_units NUMERIC(10,4),
    provider TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_picks_match_id ON picks (match_id);
CREATE INDEX idx_picks_user_created_at ON picks (user_id, created_at);
CREATE INDEX idx_picks_status_created_at ON picks (status, created_at);

CREATE TABLE results (
    id UUID PRIMARY KEY,
    pick_id UUID NOT NULL UNIQUE REFERENCES picks(id) ON DELETE CASCADE,
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

CREATE INDEX idx_results_settled_at ON results (settled_at);
CREATE INDEX idx_results_status_settled_at ON results (status, settled_at);

CREATE TABLE player_props (
    id UUID PRIMARY KEY,
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id) ON DELETE SET NULL,
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

CREATE INDEX idx_player_props_match_metric ON player_props (match_id, metric);
CREATE INDEX idx_player_props_generated_at ON player_props (generated_at);
