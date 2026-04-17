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

## New Structure

```text
backend/
  app/
    api/
      routes/
        picks.py
    core/
      config.py
    domain/
      models.py
      pricing.py
    repositories/
      contracts.py
      in_memory.py
    schemas/
      picks.py
    services/
      get_daily_picks.py
    main.py
  workers/
    README.md
  tests/
    test_get_daily_picks.py
    test_pricing.py
  requirements.txt
```

## First-Step Migration Map

Current file -> future destination

- `core/model.py`
  - pricing helpers -> `backend/app/domain/pricing.py`
  - match analysis orchestration -> `backend/app/services/analyze_match.py`
  - ranking logic -> `backend/app/services/get_daily_picks.py`
- `core/stats.py`
  - pure team and match stats -> `backend/app/domain/`
- `data/sources.py`
  - external APIs and scraping -> `backend/app/repositories/` and provider adapters
- `storage/favorites.py`
  - pick persistence -> `backend/app/repositories/` backed by PostgreSQL
- `app.py`
  - Streamlit-only presentation and user interaction
- `ui/components.py`
  - temporary legacy UI only, later replaced by frontend client

## Domain Models Introduced

- `Match`
- `OddsQuote`
- `Pick`
- `Analysis`
- `PlayerProp`

All of them live in `backend/app/domain/models.py` and are framework-free.

## First Repository Contracts

- `MatchRepository`
- `OddsRepository`
- `PickRepository`
- `ResultRepository`

These are protocols only. No database migration is required yet.

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

## Breaking Changes

None in runtime behavior yet.

The current Streamlit app is not wired into this backend skeleton in this step.

## Manual Review Points

- Confirm naming of domain fields before adding database migrations.
- Confirm if `Pick.stake_fraction` should store full Kelly or adjusted Kelly.
- Confirm whether `Match.id` is internal UUID or source external id.
- Confirm whether odds should be stored raw per provider snapshot or only normalized latest.

## Next Safe Step

Extract one real use case from the legacy app into `backend/app/services/` and make Streamlit call that service instead of calling `core/model.py` directly.
