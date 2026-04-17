# PostgreSQL Repository Design

This folder is reserved for concrete PostgreSQL repository implementations.

Planned modules:

- `matches.py`
- `odds.py`
- `picks.py`
- `results.py`
- `player_props.py`

Current contract source of truth:
- [contracts.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/repositories/contracts.py:1)

Initial schema:
- [schema.sql](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/app/repositories/postgres/schema.sql:1)

## Design notes

- `matches` stores the canonical fixture identity used by the whole product
- `odds` is append-only by snapshot time so line movement and market drift can be analyzed historically
- `analyses` stores model snapshots separately from picks so we can compare model versions over time
- `picks` stores recommendations and user-linked selections
- `results` stores settlement and ROI
- `player_props` stores generated player probabilities for historical evaluation and ranking

## ROI tracking

ROI should be queryable at multiple levels:

- per pick
- per user
- per day/week/month
- per market
- per competition
- per model version

That is why `results` references `picks`, while `picks` references `analyses`, `matches`, and optionally `users`.
