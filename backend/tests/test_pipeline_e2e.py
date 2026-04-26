from __future__ import annotations

import pytest

from backend.workers import pipeline_worker


def _snapshot(
    *,
    matches_total: int = 0,
    matches_actionable: int = 0,
    finished_matches_total: int = 0,
    odds_quotes_total: int = 0,
    matches_with_supported_odds: int = 0,
    analyses_total: int = 0,
    picks_total: int = 0,
    settlement_eligible_picks_total: int = 0,
    settlement_completed_picks_total: int = 0,
    settlement_incomplete_picks_total: int = 0,
    results_total: int = 0,
) -> pipeline_worker.PipelineSnapshot:
    return pipeline_worker.PipelineSnapshot(
        matches_total=matches_total,
        matches_actionable=matches_actionable,
        finished_matches_total=finished_matches_total,
        odds_quotes_total=odds_quotes_total,
        matches_with_supported_odds=matches_with_supported_odds,
        analyses_total=analyses_total,
        picks_total=picks_total,
        settlement_eligible_picks_total=settlement_eligible_picks_total,
        settlement_completed_picks_total=settlement_completed_picks_total,
        settlement_incomplete_picks_total=settlement_incomplete_picks_total,
        results_total=results_total,
    )


def _install_pipeline_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    after_ingestion: pipeline_worker.PipelineSnapshot,
    after_odds: pipeline_worker.PipelineSnapshot,
    after_analysis: pipeline_worker.PipelineSnapshot,
    after_settlement: pipeline_worker.PipelineSnapshot,
) -> None:
    state = {"stage": "empty"}

    monkeypatch.setattr(pipeline_worker, "create_postgres_connection_factory", lambda: object())
    monkeypatch.setattr(pipeline_worker, "_ensure_schema", lambda _connection_factory: None)

    def _run_match_ingestion() -> int:
        state["stage"] = "after_ingestion"
        return after_ingestion.matches_total

    def _run_odds_ingestion() -> int:
        state["stage"] = "after_odds"
        return after_odds.odds_quotes_total

    def _run_analysis() -> int:
        state["stage"] = "after_analysis"
        return after_analysis.picks_total

    def _run_settlement() -> int:
        state["stage"] = "after_settlement"
        return after_settlement.settlement_completed_picks_total

    def _load_snapshot(_connection_factory, _target_date):
        snapshots = {
            "after_ingestion": after_ingestion,
            "after_odds": after_odds,
            "after_analysis": after_analysis,
            "after_settlement": after_settlement,
        }
        return snapshots[state["stage"]]

    monkeypatch.setattr(pipeline_worker, "run_match_ingestion_once", _run_match_ingestion)
    monkeypatch.setattr(pipeline_worker, "run_odds_ingestion_once", _run_odds_ingestion)
    monkeypatch.setattr(pipeline_worker, "run_analysis_once", _run_analysis)
    monkeypatch.setattr(pipeline_worker, "run_settlement_once", _run_settlement)
    monkeypatch.setattr(pipeline_worker, "_load_snapshot", _load_snapshot)


def test_pipeline_e2e_succeeds_when_all_stages_produce_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_DATE", "2026-04-20")
    _install_pipeline_fakes(
        monkeypatch,
        after_ingestion=_snapshot(matches_total=4, matches_actionable=4),
        after_odds=_snapshot(
            matches_total=4,
            matches_actionable=4,
            odds_quotes_total=12,
            matches_with_supported_odds=4,
        ),
        after_analysis=_snapshot(
            matches_total=4,
            matches_actionable=4,
            finished_matches_total=1,
            odds_quotes_total=12,
            matches_with_supported_odds=4,
            analyses_total=4,
            picks_total=2,
            settlement_eligible_picks_total=1,
            settlement_incomplete_picks_total=1,
        ),
        after_settlement=_snapshot(
            matches_total=4,
            matches_actionable=4,
            finished_matches_total=1,
            odds_quotes_total=12,
            matches_with_supported_odds=4,
            analyses_total=4,
            picks_total=2,
            settlement_eligible_picks_total=1,
            settlement_completed_picks_total=1,
            settlement_incomplete_picks_total=0,
            results_total=1,
        ),
    )

    assert pipeline_worker.run_once() == 2


@pytest.mark.parametrize(
    ("after_ingestion", "after_odds", "after_analysis", "after_settlement", "expected_message"),
    [
        (
            _snapshot(),
            _snapshot(),
            _snapshot(),
            _snapshot(),
            "no matches were stored",
        ),
        (
            _snapshot(matches_total=3, matches_actionable=3),
            _snapshot(matches_total=3, matches_actionable=3),
            _snapshot(),
            _snapshot(),
            "no supported odds were stored",
        ),
        (
            _snapshot(matches_total=3, matches_actionable=3),
            _snapshot(matches_total=3, matches_actionable=3, odds_quotes_total=9, matches_with_supported_odds=3),
            _snapshot(matches_total=3, matches_actionable=3, odds_quotes_total=9, matches_with_supported_odds=3, analyses_total=3),
            _snapshot(),
            "generated_picks=0 is below required minimum=1",
        ),
        (
            _snapshot(matches_total=3, matches_actionable=3),
            _snapshot(matches_total=3, matches_actionable=3, odds_quotes_total=9, matches_with_supported_odds=3),
            _snapshot(
                matches_total=3,
                matches_actionable=3,
                finished_matches_total=1,
                odds_quotes_total=9,
                matches_with_supported_odds=3,
                analyses_total=3,
                picks_total=2,
                settlement_eligible_picks_total=1,
            ),
            _snapshot(
                matches_total=3,
                matches_actionable=3,
                finished_matches_total=1,
                odds_quotes_total=9,
                matches_with_supported_odds=3,
                analyses_total=3,
                picks_total=2,
                settlement_eligible_picks_total=1,
                settlement_completed_picks_total=0,
                settlement_incomplete_picks_total=1,
            ),
            "incomplete_settlements=1 remain",
        ),
    ],
)
def test_pipeline_e2e_fails_when_any_stage_produces_no_required_output(
    monkeypatch: pytest.MonkeyPatch,
    after_ingestion: pipeline_worker.PipelineSnapshot,
    after_odds: pipeline_worker.PipelineSnapshot,
    after_analysis: pipeline_worker.PipelineSnapshot,
    after_settlement: pipeline_worker.PipelineSnapshot,
    expected_message: str,
) -> None:
    monkeypatch.setenv("PIPELINE_DATE", "2026-04-20")
    _install_pipeline_fakes(
        monkeypatch,
        after_ingestion=after_ingestion,
        after_odds=after_odds,
        after_analysis=after_analysis,
        after_settlement=after_settlement,
    )

    with pytest.raises(pipeline_worker.PipelineWorkerError, match=expected_message):
        pipeline_worker.run_once()
