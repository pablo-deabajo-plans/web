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
- [odds_ingestion_worker.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/odds_ingestion_worker.py:1)
- [analysis_worker.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/analysis_worker.py:1)
- [settlement_worker.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/settlement_worker.py:1)
- [pipeline_worker.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/pipeline_worker.py:1)
- [scheduler.py](/C:/Users/pablo/Documents/Gordon%20BetScanner/backend/workers/scheduler.py:1)

Scheduler pipeline order:

1. `match_ingestion`
2. `odds_ingestion`
3. `analysis`
4. `settlement`

The scheduler runs jobs sequentially in that order, which avoids worker conflicts and keeps the pipeline idempotent as long as each worker remains safe to rerun.

Bootstrap pipeline:

- `pipeline_worker.py` bootstraps schema objects if needed, pins one shared local target date across all stages, runs `match_ingestion -> odds_ingestion -> analysis -> settlement`, and fails loudly when a required downstream dataset was not produced.

Minimal scheduler environment variables:

- `MATCH_INGESTION_INTERVAL_MINUTES`
- `ODDS_INGESTION_INTERVAL_MINUTES`
- `ANALYSIS_INTERVAL_MINUTES`
- `SETTLEMENT_INTERVAL_MINUTES`
