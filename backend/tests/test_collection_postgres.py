"""Job ledger, independent commits and crash recovery in a fresh PostgreSQL database."""

import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.collectors.errors import ProviderContractError, ProviderTimeoutError
from app.collectors.provider import StockInfo
from app.core.database import create_session_factory
from app.core.errors import ApplicationError
from app.jobs.collection import CollectionRunner, RetryPolicy
from app.models import DailyPrice, DataSyncJob, Stock, TechnicalIndicator
from app.repositories.sync_jobs import JobScope, SyncJobRepository
from app.services.daily_prices import DailyPriceService
from app.services.stocks import StockService
from tests.test_daily_price_service import END, START, FixtureDailyProvider, bar
from tests.test_stock_service import FixtureProvider

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def job_engine():
    value = os.getenv("JOB_TEST_DATABASE_URL")
    if not value:
        pytest.skip("JOB_TEST_DATABASE_URL requires a new empty *_jobs_test database")
    url = make_url(value)
    assert url.drivername == "postgresql+psycopg" and (url.database or "").endswith("_jobs_test")
    engine = sa.create_engine(value)
    try:
        assert sa.inspect(engine).get_table_names() == [], "Never reset an existing database"
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("APP_ENV", "test")
            patch.setenv("TEST_DATABASE_URL", value)
            command.upgrade(config, "head")
            command.check(config)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def jobs(job_engine):
    factory = create_session_factory(job_engine)
    StockService(factory).sync(
        FixtureProvider(
            tuple(StockInfo(symbol, "模拟证券", "SZ") for symbol in ("000001.SZ", "000002.SZ"))
        )
    )
    yield SyncJobRepository(job_engine)
    # Only this module's suffix-guarded newly created database is cleaned.
    with job_engine.begin() as connection:
        for model in (DataSyncJob, TechnicalIndicator, DailyPrice, Stock):
            connection.execute(sa.delete(model))


def scope(symbol="000001.SZ"):
    return JobScope("mock_fixture", "backfill", symbol, START, END)


def runner(jobs, provider):
    factory = create_session_factory(jobs.engine)
    return CollectionRunner(
        jobs,
        StockService(factory),
        DailyPriceService(factory),
        provider,
        source="mock_fixture",
        retry=RetryPolicy(3, 0),
    )


def prices(engine):
    with engine.connect() as connection:
        return connection.execute(
            sa.select(DailyPrice.__table__).order_by(DailyPrice.trade_date)
        ).all()


def test_ledger_matches_committed_rows_and_repeated_run(jobs):
    provider = FixtureDailyProvider({"000001.SZ": (bar(day=END), bar())})
    collector = runner(jobs, provider)
    first = collector.run(scope())
    assert (first.total_count, first.success_count, first.failure_count) == (1, 1, 0)
    assert first.checkpoint_symbol == "000001.SZ" and first.checkpoint_date == END
    persisted = prices(jobs.engine)
    second = collector.run(scope())
    assert first.id != second.id and prices(jobs.engine) == persisted
    assert len(jobs.list_recent()) == 2
    assert collector.resume(first.id) == first and len(provider.calls) == 2


def test_partial_then_all_failure_preserves_commits(jobs):
    provider = FixtureDailyProvider({"000001.SZ": (bar(),), "000002.SZ": ProviderContractError()})
    collector = runner(jobs, provider)
    good, bad = collector.run(scope()), collector.run(scope("000002.SZ"))
    assert (good.status, bad.status) == ("succeeded", "failed")
    assert bad.failure_count == 1 and bad.error_code == "provider_contract_error"
    committed = prices(jobs.engine)
    with jobs.engine.connect() as connection:
        first_started = connection.scalar(
            sa.select(DataSyncJob.started_at).where(DataSyncJob.id == good.id)
        )
        assert (
            connection.scalar(sa.select(DataSyncJob.finished_at).where(DataSyncJob.id == good.id))
            is not None
        )
    provider.data["000001.SZ"] = ProviderTimeoutError()
    failed = collector.run(scope())
    assert failed.status == "failed" and failed.checkpoint_date is None
    assert prices(jobs.engine) == committed
    assert len([call for call in provider.calls if call[0] == "000001.SZ"]) == 4
    provider.data["000001.SZ"] = (bar(), bar(day=END))
    assert collector.resume(failed.id).success_count == 1 and len(prices(jobs.engine)) == 2
    with jobs.engine.connect() as connection:
        assert (
            connection.scalar(sa.select(DataSyncJob.started_at).where(DataSyncJob.id == failed.id))
            > first_started
        )


def test_commit_before_job_finish_crash_replays_idempotently(jobs, monkeypatch):
    provider = FixtureDailyProvider({"000001.SZ": (bar(), bar(day=END))})
    collector = runner(jobs, provider)
    original = jobs.finish
    monkeypatch.setattr(jobs, "finish", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        collector.run(scope())
    pending = jobs.list_recent()[0]
    assert pending.status == "running" and pending.checkpoint_date is None
    committed = prices(jobs.engine)
    assert len(committed) == 2
    monkeypatch.setattr(jobs, "finish", original)
    resumed = collector.resume(pending.id)
    assert resumed.id == pending.id and resumed.checkpoint_date == END
    assert prices(jobs.engine) == committed and provider.calls[0] == provider.calls[1]


def test_pending_duplicate_guard_and_resume(jobs):
    pending = jobs.create(scope())
    with pytest.raises(ApplicationError) as error:
        runner(jobs, FixtureDailyProvider()).run(scope())
    assert error.value.code == "active_job_exists"
    assert runner(jobs, FixtureDailyProvider()).resume(pending.id).status == "succeeded"
    done = jobs.get(pending.id)
    assert done.success_count == 1 and done.error_code == "empty_response_coverage_unverified"
    assert done.checkpoint_date is None and prices(jobs.engine) == []


def test_global_mutex_other_connection_and_release(jobs):
    other = SyncJobRepository(jobs.engine)
    with jobs.ownership():
        with pytest.raises(ApplicationError) as error:
            runner(other, FixtureDailyProvider()).run(replace(scope(), job_type="incremental"))
        assert error.value.code == "collection_busy" and other.list_recent() == ()
        # Dedicated session is idle, not holding a business transaction during upstream I/O.
        with jobs.engine.connect() as connection:
            state = connection.execute(
                sa.text(
                    "SELECT state, xact_start FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND query = 'SELECT pg_try_advisory_lock(7348190501)'"
                )
            ).all()
        assert any(row.state == "idle" and row.xact_start is None for row in state)
    with other.ownership():
        pass
    with pytest.raises(RuntimeError), jobs.ownership():
        raise RuntimeError("fixture")
    with other.ownership():
        pass


def test_wrong_provenance_never_writes(jobs):
    provider = FixtureDailyProvider({"000001.SZ": (bar(),)})
    original = provider.fetch_daily_prices
    provider.fetch_daily_prices = lambda *args: replace(original(*args), source="other_source")
    job = runner(jobs, provider).run(scope())
    assert job.error_code == "provider_source_mismatch" and prices(jobs.engine) == []


def test_stock_snapshot_counts_and_failure_unknown_total(jobs):
    provider = FixtureProvider((StockInfo("600519.SH", "模拟证券", "SH"),))
    collector = runner(jobs, provider)
    job = collector.run(JobScope("mock_fixture", "full"))
    assert (job.total_count, job.success_count, job.checkpoint_symbol) == (1, 1, "600519.SH")
    provider.fetch_stocks = Mock(side_effect=ProviderContractError())
    failed = collector.run(JobScope("mock_fixture", "full"))
    assert failed.status == "failed" and failed.total_count == failed.failure_count == 0


def test_sigkill_releases_ownership_and_preserves_running_job(jobs, tmp_path):
    marker = tmp_path / "started"
    code = """
import os,time
from pathlib import Path
import sqlalchemy as sa
from app.repositories.sync_jobs import SyncJobRepository,JobScope
from app.jobs.collection import CollectionRunner
from app.core.database import create_session_factory
from app.services.stocks import StockService
from app.services.daily_prices import DailyPriceService
from datetime import date
class BlockingProvider:
    def fetch_daily_prices(self,*args):
        Path(os.environ['FIXTURE_MARKER']).write_text('ready')
        time.sleep(30)
engine=sa.create_engine(os.environ['JOB_TEST_DATABASE_URL'])
factory=create_session_factory(engine)
CollectionRunner(SyncJobRepository(engine),StockService(factory),DailyPriceService(factory),BlockingProvider(),source='mock_fixture').run(JobScope('mock_fixture','backfill','000001.SZ',date(2026,9,28),date(2026,9,29)))
"""
    root = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        env=dict(os.environ, PYTHONPATH=str(root), FIXTURE_MARKER=str(marker)),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists(), "Child must reach provider after committing running state"
        active = jobs.list_recent()[0]
        assert active.status == "running"
        with pytest.raises(ApplicationError) as error:
            runner(jobs, FixtureDailyProvider()).resume(active.id)
        assert error.value.code == "collection_busy"
    finally:
        process.kill()
        process.wait(timeout=5)
    assert process.returncode == -9
    resumed = runner(jobs, FixtureDailyProvider({"000001.SZ": (bar(),)})).resume(active.id)
    assert (
        resumed.id == active.id and resumed.status == "succeeded" and len(prices(jobs.engine)) == 1
    )


def test_actual_cli_partial_failed_inspection_and_resume_offline(jobs, tmp_path):
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests/fixtures/akshare/daily.json"
    (tmp_path / "akshare.py").write_text(f"""
from pathlib import Path
class Frame:
    columns=[]
    def to_json(self,**kwargs): return Path({str(fixture)!r}).read_text()
def stock_zh_a_hist(**kwargs):
    print('password=fixture-secret')
    if kwargs['symbol']=='000002': raise KeyError('password=fixture-secret')
    return Frame()
""")
    (tmp_path / "requests").mkdir()
    (tmp_path / "requests/__init__.py").write_text("")
    (tmp_path / "requests/exceptions.py").write_text("class Timeout(Exception): pass\n")
    env = dict(
        os.environ,
        APP_ENV="test",
        TEST_DATABASE_URL=os.environ["JOB_TEST_DATABASE_URL"],
        PYTHONPATH=os.pathsep.join([str(tmp_path), str(root)]),
    )

    def cli(*args):
        result = subprocess.run(
            [sys.executable, "-m", "app.jobs.cli", "--retry-delay", "0", *args],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert "fixture-secret" not in result.stdout + result.stderr
        return result.returncode, [json.loads(line) for line in result.stdout.splitlines()]

    args = ("--start", "2026-09-28", "--end", "2026-09-29")
    code, output = cli("daily", "--symbol", "000001.SZ", "--symbol", "000002.SZ", *args)
    assert code == 1 and output[-1]["status"] == "partial" and output[-1]["failed_jobs"] == 1
    assert len(prices(jobs.engine)) == 2
    bad = next(job for job in jobs.list_recent() if job.status == "failed")
    code, output = cli("resume", str(bad.id))
    assert code == 1 and output[-1]["status"] == "failed"
    good = next(job for job in jobs.list_recent() if job.status == "succeeded")
    assert cli("resume", str(good.id))[0] == 0
    code, output = cli("jobs", "--limit", "2")
    assert code == 0 and len(output) == 2
    assert all(item["coverage_verified"] is False for item in output)
    # M4 manual incremental rehearsal retains prices and versioned indicators.
    code, output = cli("daily", "--symbol", "000001.SZ", *args, "--job-type", "incremental")
    assert code == 0 and output[-1]["status"] == "succeeded"
    assert len(prices(jobs.engine)) == 2
    with jobs.engine.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(TechnicalIndicator)) == 2
    assert any(job.scope.job_type == "incremental" for job in jobs.list_recent())


def test_cli_sigterm_cleanup_and_resume(jobs, tmp_path):
    root = Path(__file__).resolve().parents[1]
    marker = tmp_path / "worker.pid"
    fixture = root / "tests/fixtures/akshare/daily.json"
    sdk = tmp_path / "akshare.py"
    sdk.write_text(f"""
import os,time
from pathlib import Path
def stock_zh_a_hist(**kwargs):
    Path({str(marker)!r}).write_text(str(os.getpid()))
    time.sleep(30)
""")
    (tmp_path / "requests").mkdir()
    (tmp_path / "requests/__init__.py").write_text("")
    (tmp_path / "requests/exceptions.py").write_text("class Timeout(Exception): pass\n")
    env = dict(
        os.environ,
        APP_ENV="test",
        TEST_DATABASE_URL=os.environ["JOB_TEST_DATABASE_URL"],
        PYTHONPATH=os.pathsep.join([str(tmp_path), str(root)]),
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.jobs.cli",
            "daily",
            "--symbol",
            "000001.SZ",
            "--start",
            "2026-09-28",
            "--end",
            "2026-09-29",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 130 and "collection_interrupted" in stdout
        assert "Traceback" not in stdout + stderr
        with pytest.raises(ProcessLookupError):
            os.kill(int(marker.read_text()), 0)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    active = jobs.list_recent()[0]
    assert active.status == "running" and active.checkpoint_date is None
    sdk.write_text(f"""
from pathlib import Path
class Frame:
    columns=[]
    def to_json(self,**kwargs): return Path({str(fixture)!r}).read_text()
def stock_zh_a_hist(**kwargs): return Frame()
""")
    result = subprocess.run(
        [sys.executable, "-m", "app.jobs.cli", "resume", str(active.id)],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0 and jobs.get(active.id).status == "succeeded"
    assert len(prices(jobs.engine)) == 2
