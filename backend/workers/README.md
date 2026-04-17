# Workers

These jobs are the path away from request-time recomputation.

Target behavior:

- fetch matches on a schedule
- fetch odds on a schedule
- precompute picks and player props ahead of API reads

The API layer should only read stored outputs. It should not call heavy model logic on request.

Implemented worker entrypoints:

- [ingest_matches.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/ingest_matches.py:1)
- [ingest_odds.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/ingest_odds.py:1)
- [precompute_analyses.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/precompute_analyses.py:1)
