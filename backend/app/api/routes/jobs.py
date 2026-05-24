from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.workers.analysis_worker import run_once as run_analysis_once
from backend.workers.match_ingestion_worker import run_once as run_match_ingestion_once
from backend.workers.odds_ingestion_worker import run_once as run_odds_ingestion_once
from backend.workers.settlement_worker import run_once as run_settlement_once

router = APIRouter()

_RUNNERS = {
    "match_ingestion": run_match_ingestion_once,
    "odds_ingestion": run_odds_ingestion_once,
    "analysis": run_analysis_once,
    "settlement": run_settlement_once,
}


@router.post("/trigger/{job_name}", tags=["jobs"])
def trigger_job(job_name: str, background_tasks: BackgroundTasks):
    runner = _RUNNERS.get(job_name)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name}")
    background_tasks.add_task(runner)
    return {"job": job_name, "status": "queued"}
