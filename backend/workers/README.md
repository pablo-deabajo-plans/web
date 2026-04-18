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
- [match_ingestion_worker.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/match_ingestion_worker.py:1)
- [analysis_worker.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/analysis_worker.py:1)
- [settlement_worker.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/settlement_worker.py:1)
- [scheduler.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/scheduler.py:1)

Scheduler pipeline order:

1. `match_ingestion`
2. `analysis`
3. `settlement`

The scheduler runs jobs sequentially in that order, which avoids worker conflicts and keeps the pipeline idempotent as long as each worker remains safe to rerun.

Minimal scheduler environment variables:

- `MATCH_INGESTION_INTERVAL_MINUTES`
- `ANALYSIS_INTERVAL_MINUTES`
- `SETTLEMENT_INTERVAL_MINUTES`
