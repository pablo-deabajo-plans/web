from __future__ import annotations

import argparse
import os

import pytest
import uvicorn

from backend.app.core.logging import configure_logging, get_logger
from backend.app.repositories.postgres.bootstrap import ensure_postgres_schema
from backend.app.repositories.postgres.connection import create_postgres_connection_factory
from backend.workers.pipeline_worker import run_once as run_pipeline_once


LOGGER = get_logger(__name__)


def _run_pipeline() -> None:
    processed = run_pipeline_once()
    LOGGER.info("Pipeline completed picks=%s", processed)


def _run_api(host: str, port: int) -> None:
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)


def _run_tests(pytest_args: list[str]) -> None:
    args = pytest_args or ["backend/tests"]
    exit_code = pytest.main(args)
    if exit_code != 0:
        raise SystemExit(exit_code)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local runner for Gordon BetScanner backend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup", help="Create required database objects")
    subparsers.add_parser("pipeline", help="Run the end-to-end pipeline once")

    api_parser = subparsers.add_parser("api", help="Start the FastAPI server")
    api_parser.add_argument("--host", default=os.getenv("API_HOST", "127.0.0.1"))
    api_parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", "8000")))

    test_parser = subparsers.add_parser("test", help="Run pytest")
    test_parser.add_argument("pytest_args", nargs="*")

    all_parser = subparsers.add_parser("all", help="Setup DB, run pipeline, then start API")
    all_parser.add_argument("--host", default=os.getenv("API_HOST", "127.0.0.1"))
    all_parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", "8000")))

    return parser


def main() -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "setup":
        ensure_postgres_schema(create_postgres_connection_factory())
        return 0

    if args.command == "pipeline":
        _run_pipeline()
        return 0

    if args.command == "api":
        _run_api(args.host, args.port)
        return 0

    if args.command == "test":
        _run_tests(args.pytest_args)
        return 0

    if args.command == "all":
        ensure_postgres_schema(create_postgres_connection_factory())
        _run_pipeline()
        _run_api(args.host, args.port)
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
