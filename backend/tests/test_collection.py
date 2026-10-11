"""Deterministic orchestration and argument safety; no network or database."""

from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.collectors.errors import ProviderContractError, ProviderTimeoutError
from app.core.errors import ApplicationError
from app.jobs.cli import main
from app.jobs.collection import CollectionRunner, RetryPolicy
from app.repositories.sync_jobs import JobScope, JobView
from tests.test_daily_price_service import END, START


class MemoryJobs:
    def __init__(self):
        self.rows = {}
        self.owned = False

    @contextmanager
    def ownership(self):
        assert not self.owned
        self.owned = True
        try:
            yield
        finally:
            self.owned = False

    def create(self, scope):
        job = JobView(uuid4(), scope, "pending", int(bool(scope.symbol)), 0, 0, None, None, None)
        self.rows[job.id] = job
        return job

    def get(self, job_id):
        return self.rows[job_id]

    def start(self, job_id):
        self.rows[job_id] = replace(
            self.get(job_id), status="running", success_count=0, failure_count=0
        )

    def finish(
        self, job_id, *, total, code=None, empty=False, checkpoint_symbol=None, checkpoint_date=None
    ):
        job = replace(
            self.get(job_id),
            status="failed" if code else "succeeded",
            total_count=total,
            success_count=0 if code else total,
            failure_count=total if code else 0,
            error_code=code or ("empty_response_coverage_unverified" if empty else None),
            checkpoint_symbol=checkpoint_symbol,
            checkpoint_date=checkpoint_date,
        )
        self.rows[job_id] = job
        return job


def receipt(count=2):
    return SimpleNamespace(
        processed_count=count,
        last_trade_date=END if count else None,
        last_symbol="600519.SH" if count else None,
    )


def setup_runner(effects):
    jobs, service, delays = MemoryJobs(), Mock(), []
    service.sync.side_effect = effects
    runner = CollectionRunner(
        jobs,
        service,
        service,
        Mock(),
        source="mock_fixture",
        retry=RetryPolicy(3, 2),
        sleep=delays.append,
    )
    return runner, jobs, service, delays


def scope():
    return JobScope("mock_fixture", "backfill", "000001.SZ", START, END)


def test_retry_and_completed_resume():
    runner, jobs, service, delays = setup_runner([ProviderTimeoutError(), receipt()])
    job = runner.run(scope())
    assert (job.status, job.success_count, job.checkpoint_date) == ("succeeded", 1, END)
    assert delays == [2] and service.sync.call_count == 2
    assert runner.resume(job.id) == job
    assert service.sync.call_count == 2 and not jobs.owned


def test_exhaustion_and_failed_resume_reset_counts():
    runner, _, service, delays = setup_runner([ProviderTimeoutError()] * 3 + [receipt()])
    job = runner.run(scope())
    assert (job.status, job.failure_count, job.error_code) == ("failed", 1, "provider_timeout")
    assert job.checkpoint_date is None and delays == [2, 4]
    resumed = runner.resume(job.id)
    assert resumed.id == job.id and resumed.success_count == 1 and resumed.failure_count == 0
    assert service.sync.call_count == 4


@pytest.mark.parametrize(
    "error", [ProviderContractError(), ApplicationError("storage_error", "safe", 503)]
)
def test_permanent_failure_no_retry(error):
    runner, _, service, delays = setup_runner([error])
    assert runner.run(scope()).error_code == error.code
    assert service.sync.call_count == 1 and delays == []


def test_interruption_keeps_running_then_replays_exact_scope():
    runner, jobs, service, _ = setup_runner([KeyboardInterrupt(), receipt()])
    with pytest.raises(KeyboardInterrupt):
        runner.run(scope())
    job = next(iter(jobs.rows.values()))
    assert job.status == "running" and not jobs.owned
    assert runner.resume(job.id).status == "succeeded"
    assert service.sync.call_args_list[0] == service.sync.call_args_list[1]


def test_unexpected_error_safe_record():
    runner, jobs, _, _ = setup_runner([RuntimeError("secret-url")])
    with pytest.raises(RuntimeError):
        runner.run(scope())
    assert next(iter(jobs.rows.values())).error_code == "collection_internal_error"


@pytest.mark.parametrize("daily,count", [(True, 0), (False, 0), (False, 2)])
def test_work_items_and_empty_semantics(daily, count):
    runner, _, _, _ = setup_runner([receipt(count)])
    job = runner.run(scope() if daily else JobScope("mock_fixture", "full"))
    assert job.total_count == (1 if daily else count)
    assert job.success_count == job.total_count
    if count == 0:
        assert job.error_code == "empty_response_coverage_unverified"
        assert job.checkpoint_symbol is None and job.checkpoint_date is None


@pytest.mark.parametrize(
    "attempts,delay", [(0, 1), (6, 1), (True, 1), (3, -1), (3, float("nan")), (3, float("inf"))]
)
def test_retry_bounds(attempts, delay):
    with pytest.raises(ApplicationError):
        RetryPolicy(attempts, delay)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["daily"],
        ["--max-attempts", "0", "stocks"],
        ["--retry-delay", "nan", "stocks"],
        ["resume", "secret-url"],
        ["jobs", "--limit", "101"],
        ["secret-url"],
        [
            "daily",
            "--symbol",
            "000001.SZ",
            "--symbol",
            "000001.sz",
            "--start",
            "2026-09-28",
            "--end",
            "2026-09-29",
        ],
        [
            "daily",
            "--symbol",
            "000001.SZ",
            "--symbol",
            "secret-url",
            "--start",
            "2026-09-28",
            "--end",
            "2026-09-29",
        ],
        ["daily", "--symbol", "000001.SZ", "--start", "2026-09-29", "--end", "2026-09-28"],
    ],
)
def test_invalid_arguments_before_engine(args, monkeypatch, capsys):
    engine = Mock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr("app.jobs.cli.create_configured_database_engine", engine)
    assert main(args) == 2
    engine.assert_not_called()
    assert "secret-url" not in capsys.readouterr().out


def test_help_without_engine(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0 and "resume" in capsys.readouterr().out
