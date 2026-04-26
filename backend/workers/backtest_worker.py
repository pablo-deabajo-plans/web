from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.logging import configure_logging, get_logger
from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.app.services.backtesting import BacktestingService
from backend.workers.metrics import store_metric


LOGGER = get_logger(__name__)


def _resolve_date(env_name: str, *, default: date | None = None) -> date:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        if default is None:
            raise ValueError(f"{env_name} must be set")
        return default
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must use YYYY-MM-DD format") from exc


def _log_worker_error(*, context: str, error: Exception) -> None:
    LOGGER.exception(
        json.dumps(
            {
                "event": "worker_failure",
                "worker": "backtest",
                "context": context,
                "source": "backtest",
                "league": None,
                "match_id": None,
                "error_type": type(error).__name__,
                "error": str(error),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )


def run_once() -> str:
    start_date = _resolve_date("BACKTEST_START_DATE")
    end_date = _resolve_date("BACKTEST_END_DATE", default=start_date)
    pipeline_run_id = os.getenv("PIPELINE_RUN_ID", str(uuid4()))

    connection_factory = create_postgres_connection_factory()
    ensure_postgres_schema(connection_factory)
    service = BacktestingService(connection_factory)
    result = service.run(start_date=start_date, end_date=end_date)

    store_metric(
        connection_factory,
        metric_name="backtest_total_picks",
        worker_name="backtest",
        pipeline_run_id=pipeline_run_id,
        target_date=end_date,
        metric_value=result.total_picks,
    )
    store_metric(
        connection_factory,
        metric_name="backtest_summary",
        worker_name="backtest",
        pipeline_run_id=pipeline_run_id,
        target_date=end_date,
        json_value=json.dumps(
            {
                "run_id": result.run_id,
                "start_date": result.start_date.isoformat(),
                "end_date": result.end_date.isoformat(),
                "total_matches": result.total_matches,
                "analyzed_matches": result.analyzed_matches,
                "total_picks": result.total_picks,
                "roi": result.summary.roi,
                "hit_rate": result.summary.hit_rate,
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
    )
    return result.run_id


def main() -> int:
    configure_logging()
    try:
        run_id = run_once()
        LOGGER.info("Backtest worker completed run_id=%s", run_id)
    except (RuntimeError, ValueError) as exc:
        _log_worker_error(context="main", error=exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

