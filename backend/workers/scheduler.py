from __future__ import annotations

import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.workers.analysis_worker import run_once as run_analysis_once
from backend.workers.match_ingestion_worker import run_once as run_match_ingestion_once
from backend.workers.settlement_worker import run_once as run_settlement_once


LOGGER = get_logger(__name__)
STOP_REQUESTED = False


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    interval_seconds: int
    runner: Callable[[], int]


def _read_interval_seconds(env_name: str, default_minutes: int) -> int:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return default_minutes * 60
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be an integer number of minutes") from exc
    if value <= 0:
        raise ValueError(f"{env_name} must be greater than zero")
    return value * 60


def _build_jobs() -> list[ScheduledJob]:
    return [
        ScheduledJob(
            name="match_ingestion",
            interval_seconds=_read_interval_seconds("MATCH_INGESTION_INTERVAL_MINUTES", 15),
            runner=run_match_ingestion_once,
        ),
        ScheduledJob(
            name="analysis",
            interval_seconds=_read_interval_seconds("ANALYSIS_INTERVAL_MINUTES", 15),
            runner=run_analysis_once,
        ),
        ScheduledJob(
            name="settlement",
            interval_seconds=_read_interval_seconds("SETTLEMENT_INTERVAL_MINUTES", 15),
            runner=run_settlement_once,
        ),
    ]


def _handle_signal(signum, _frame) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    LOGGER.info("Scheduler received shutdown signal signum=%s", signum)


def _install_signal_handlers() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


def _run_job(job: ScheduledJob) -> None:
    started_at = time.monotonic()
    try:
        processed = job.runner()
        elapsed = time.monotonic() - started_at
        LOGGER.info(
            "Scheduler job completed job=%s processed=%s duration_seconds=%.2f",
            job.name,
            processed,
            elapsed,
        )
    except Exception:
        elapsed = time.monotonic() - started_at
        LOGGER.exception(
            "Scheduler job failed job=%s duration_seconds=%.2f",
            job.name,
            elapsed,
        )


def run_forever() -> int:
    jobs = _build_jobs()
    next_run_at = {job.name: time.monotonic() for job in jobs}

    LOGGER.info(
        "Scheduler started jobs=%s",
        ", ".join(f"{job.name}:{job.interval_seconds}s" for job in jobs),
    )

    while not STOP_REQUESTED:
        now = time.monotonic()
        for job in jobs:
            if now < next_run_at[job.name]:
                continue
            # Jobs run sequentially in pipeline order so downstream workers
            # always observe the latest committed outputs from upstream workers.
            _run_job(job)
            next_run_at[job.name] = time.monotonic() + job.interval_seconds
        time.sleep(1)

    LOGGER.info("Scheduler stopped")
    return 0


def main() -> int:
    configure_logging()
    _install_signal_handlers()
    try:
        return run_forever()
    except Exception:
        LOGGER.exception("Scheduler crashed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
