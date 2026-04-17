# Backend Migration Step 01

This is the first safe migration step from the current Streamlit prototype to a production-ready backend.

## Intent

Create a parallel `backend/` skeleton without rewiring the current app yet.

That means:
- the current Streamlit app keeps working as-is
- new backend code is additive and isolated
- core betting primitives move into a pure domain layer
- a first service and a first API route exist as the reference pattern
- tests start covering business rules outside Streamlit

## Final Target Structure

```text
backend/
  app/
    api/
      routes/
        picks.py
        matches.py
        history.py
    core/
      config.py
      logging.py
    domain/
      models.py
      pricing.py
      stats.py
      analysis.py
      player_props.py
    repositories/
      contracts.py
      in_memory.py
      postgres/
    schemas/
      picks.py
      matches.py
      history.py
    services/
      get_daily_picks.py
      analyze_match.py
      compute_player_props.py
    main.py
  workers/
    README.md
    ingest_matches.py
    ingest_odds.py
    precompute_analyses.py
  tests/
    test_get_daily_picks.py
    test_pricing.py
    test_analysis.py
    test_player_props.py
  requirements.txt
```

## Existing File -> Final Location

Current file -> future destination

- `core/model.py`
  - pricing helpers -> `backend/app/domain/pricing.py`
  - simulation and match analysis rules -> `backend/app/domain/analysis.py`
  - player props rules -> `backend/app/domain/player_props.py`
  - service orchestration -> `backend/app/services/analyze_match.py`
- `core/stats.py`
  - pure team and match stats -> `backend/app/domain/stats.py`
- `data/sources.py`
  - external APIs and scraping -> `backend/app/repositories/` and provider adapters
- `storage/favorites.py`
  - pick persistence -> `backend/app/repositories/` backed by PostgreSQL
- `app.py`
  - Streamlit-only presentation and user interaction
- `ui/components.py`
  - temporary legacy UI only, later replaced by frontend client
- `data/teams.py`
  - keep as pure shared normalization module initially, later move to `backend/app/domain/teams.py`

## Target Responsibilities By Layer

- `backend/app/domain/`
  - Pure business rules, pricing, simulation, stats aggregation, player-prop probability logic
  - No Streamlit, no HTTP clients, no filesystem, no database
- `backend/app/services/`
  - Use-case orchestration such as daily picks, match analysis, and player prop computation
  - Can coordinate repositories and domain functions, but should not render UI
- `backend/app/repositories/`
  - External IO boundaries: APIs, persistence, cache storage
  - Replace direct `requests`, JSON files, and ad hoc source normalization from the legacy app
- `backend/app/api/`
  - FastAPI routes and dependency wiring only
- `backend/workers/`
  - Background ingestion and precompute jobs so the API serves prebuilt reads instead of recomputing on request

## Detailed Migration Matrix

Current module -> target layer -> target module

- `app.py`
  - legacy Streamlit shell only
  - future role: presentation client that calls backend services or API
- `ui/components.py`
  - temporary legacy presentation layer
  - future destination: frontend client or a much thinner `ui/legacy/`
- `core/model.py`
  - compatibility facade
  - target modules:
    - `backend/app/domain/pricing.py`
    - `backend/app/domain/analysis.py`
    - `backend/app/domain/player_props.py`
    - `backend/app/services/analyze_match.py`
- `core/stats.py`
  - compatibility facade
  - target module: `backend/app/domain/stats.py`
- `data/sources.py`
  - split by responsibility:
    - ESPN/football-data/Sportmonks clients -> `backend/app/repositories/providers/`
    - match loading and odds loading -> `backend/app/repositories/`
    - cache and token resolution -> `backend/app/core/config.py` plus repository adapters
- `data/teams.py`
  - team normalization and alias resolution
  - target module: `backend/app/domain/teams.py`
- `storage/favorites.py`
  - persistence adapter
  - target modules:
    - `backend/app/repositories/picks.py`
    - later PostgreSQL implementation under `backend/app/repositories/postgres/`

## Domain Models

- `Match`
- `OddsQuote`
- `Pick`
- `Analysis`
- `PlayerProp`

Current canonical definitions live in `backend/app/domain/models.py` and are framework-free.

### Model Intent

- `Match`
  - Canonical fixture identity and scheduling record
- `OddsQuote`
  - Snapshot of a bookmaker price for a specific market and selection
- `Pick`
  - Model recommendation with probability, price, edge, and stake
- `Analysis`
  - Match-level probability output plus traceability and market outputs
- `PlayerProp`
  - Per-player metric probability output for a given line

## First Repository Contracts

- `MatchRepository`
- `OddsRepository`
- `PickRepository`
- `ResultRepository`

These are protocols only. No database migration is required yet.

Current contract definitions live in [backend/app/repositories/contracts.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/repositories/contracts.py:1).

Reference in-memory implementations live in [backend/app/repositories/in_memory.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/repositories/in_memory.py:1).

## PostgreSQL Target Schema

Planned relational model for the next migration steps:

- `users`
  - `id`, `email`, `hashed_password`, `created_at`
- `matches`
  - `id`, `external_id`, `competition`, `kickoff_at`, `home_team`, `away_team`, `status`
- `odds`
  - `id`, `match_id`, `market`, `selection`, `sportsbook`, `decimal_odds`, `captured_at`
- `analyses`
  - `id`, `match_id`, `model_version`, `generated_at`, `home_win_prob`, `draw_prob`, `away_win_prob`, `expected_home_goals`, `expected_away_goals`
- `picks`
  - `id`, `user_id`, `match_id`, `market`, `selection`, `probability`, `fair_odds`, `offered_odds`, `edge`, `stake_fraction`, `provider`, `created_at`
- `results`
  - `id`, `pick_id`, `status`, `profit_units`, `settled_at`
- `player_props`
  - `id`, `match_id`, `player_id`, `player_name`, `metric`, `line`, `probability`, `expected_value`, `confidence_label`, `generated_at`

The first SQL draft now lives in [backend/app/repositories/postgres/schema.sql](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/repositories/postgres/schema.sql:1).

### Relationship design

- `users 1 -> N picks`
- `matches 1 -> N odds`
- `matches 1 -> N analyses`
- `matches 1 -> N picks`
- `matches 1 -> N player_props`
- `analyses 1 -> N picks`
- `analyses 1 -> N player_props`
- `picks 1 -> 1 results`

### ROI tracking fields

To support real performance tracking, the schema includes:

- `picks.stake_fraction`
- `picks.stake_units`
- `results.profit_units`
- `results.roi`
- `picks.provider`
- `analyses.model_version`
- `results.settled_at`

This allows ROI breakdown by market, competition, model version, time range, and user.

## Workers / Data Pipeline

Heavy work is now explicitly assigned to worker entrypoints under [backend/workers](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/README.md:1):

- [ingest_matches.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/ingest_matches.py:1)
  - fetches and upserts matches
- [ingest_odds.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/ingest_odds.py:1)
  - fetches and upserts odds snapshots
- [precompute_analyses.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/precompute_analyses.py:1)
  - persists picks and player props before API reads

Design rule:

- workers write
- API reads
- expensive model execution moves out of request time

## API Layer

FastAPI routes now exist for the required read surface:

- `GET /picks`
- `GET /matches`
- `GET /match/{id}`
- `GET /history`

Main app entrypoint:
- [backend/app/main.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/main.py:1)

Route modules:
- [backend/app/api/routes/picks.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/api/routes/picks.py:1)
- [backend/app/api/routes/matches.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/api/routes/matches.py:1)
- [backend/app/api/routes/match.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/api/routes/match.py:1)
- [backend/app/api/routes/history.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/api/routes/history.py:1)

Pydantic schemas:
- [backend/app/schemas/picks.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/schemas/picks.py:1)
- [backend/app/schemas/matches.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/schemas/matches.py:1)
- [backend/app/schemas/history.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/schemas/history.py:1)

API dependency wiring:
- [backend/app/api/dependencies.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/api/dependencies.py:1)

## Performance Improvements

The first performance pass is now implemented in two places:

### 1. Analytical probabilities instead of heavy Monte Carlo

Match simulation in [backend/app/domain/analysis.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/domain/analysis.py:1) no longer relies on random Poisson sampling for core read paths.

What changed:

- `1X2`, `BTTS`, `Over/Under 2.5`, clean sheets, and corner threshold markets are computed analytically from Poisson distributions
- expected totals for goals, corners, cards, shots, and shots on target are returned directly from model means
- top scorelines are derived from Poisson score matrices instead of 50,000 random draws

Why it matters:

- removes expensive recomputation on repeated reads
- eliminates output jitter between identical requests
- improves latency in both API and legacy Streamlit reads because `core/model.py` now delegates to this backend domain

### 2. Caching per use case

A shared in-memory TTL cache now lives in [backend/app/core/cache.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/core/cache.py:1).

Current cache strategy:

- daily picks: cached by `date + limit`
- matches: cached by `date`
- match detail: cached by `match_id`
- history: cached by `date`

Service integration:

- [backend/app/services/get_daily_picks.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/services/get_daily_picks.py:1)
- [backend/app/services/get_matches.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/services/get_matches.py:1)
- [backend/app/services/get_match_detail.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/services/get_match_detail.py:1)
- [backend/app/services/get_history.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/services/get_history.py:1)

TTL settings are configurable in [backend/app/core/config.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/core/config.py:1).

### Suggested next optimization

The next high-value step is to move legacy `descargar_resumen_espn` and daily ranking precompute fully into workers so Streamlit stops building league rankings on demand.

## Breaking Changes

None in runtime behavior yet.

The current Streamlit app is not wired into this backend skeleton in this step.

## Manual Review Points

- Confirm naming of domain fields before adding database migrations.
- Confirm if `Pick.stake_fraction` should store full Kelly or adjusted Kelly.
- Confirm whether `Match.id` is internal UUID or source external id.
- Confirm whether odds should be stored raw per provider snapshot or only normalized latest.

## Domain Extraction Status

Already extracted into `backend/app/domain/`:
- `pricing.py`
- `stats.py`
- `analysis.py`
- `player_props.py`

Legacy compatibility:
- `core/model.py` now acts as a compatibility facade over the backend domain
- `core/stats.py` now acts as a compatibility facade over the backend domain

This keeps the Streamlit app working while the pure domain becomes the real source of truth.

## Ongoing Legacy Reduction

The latest safe migration steps also started reducing three major hotspots:

- `app.py`
  - now uses dedicated services for match analysis and player props instead of calling only legacy `core/model.py` wrappers
- `data/sources.py`
  - now delegates ESPN and Sportmonks HTTP calls to provider clients under `backend/app/repositories/providers/`
- `backend/app/repositories/postgres/`
  - now contains concrete repository implementations for matches, odds, picks, and results on top of the SQL schema

## Extraction Rules

Every module in `backend/app/domain/` must respect these rules:

- no Streamlit imports
- no `requests`
- no filesystem access
- no database access
- deterministic inputs/outputs except for explicitly stochastic simulation functions
- business logic lives here first; legacy `core/` modules should only re-export or bridge temporarily
