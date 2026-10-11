"""Isolated simulated-data indicator and status integration, never developer rows."""

import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from httpx2 import ASGITransport, AsyncClient

from alembic import command
from app.core.config import Settings
from app.core.database import create_session_factory
from app.main import create_app
from app.models import DailyPrice, DataSyncJob, Stock, TechnicalIndicator
from app.services.daily_prices import DailyPriceService
from tests.test_daily_price_service import FETCHED, FixtureDailyProvider, bar

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def indicator_engine():
    value = os.getenv("INDICATOR_TEST_DATABASE_URL")
    if not value:
        pytest.skip("INDICATOR_TEST_DATABASE_URL requires a new *_indicators_test database")
    assert sa.engine.make_url(value).database.endswith("_indicators_test")
    engine = sa.create_engine(value)
    assert sa.inspect(engine).get_table_names() == []
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("APP_ENV", "test")
        patch.setenv("TEST_DATABASE_URL", value)
        command.upgrade(config, "head")
        command.check(config)
    yield engine
    engine.dispose()


@pytest.fixture
def market(indicator_engine):
    engine = indicator_engine
    with engine.begin() as conn:
        conn.execute(
            sa.insert(Stock),
            {"symbol": "000001.SZ", "name": "模拟指标", "exchange": "SZ", "status": "listed"},
        )
    yield engine, DailyPriceService(create_session_factory(engine))
    with engine.begin() as conn:
        for model in (DataSyncJob, TechnicalIndicator, DailyPrice, Stock):
            conn.execute(sa.delete(model))


def data(count=65):
    return tuple(
        bar(
            day=date(2026, 1, 5) + timedelta(days=(i // 5) * 7 + i % 5),
            open=Decimal(i + 1),
            high=Decimal(i + 2),
            low=Decimal(i),
            close=Decimal(i + 1),
        )
        for i in range(count)
    )


def snapshot(engine):
    with engine.connect() as conn:
        return (
            conn.execute(
                sa.select(TechnicalIndicator.__table__).order_by(TechnicalIndicator.trade_date)
            )
            .mappings()
            .all()
        )


def collect(service, rows):
    return service.sync(
        FixtureDailyProvider({"000001.SZ": rows}),
        "000001.SZ",
        rows[0].trade_date,
        rows[-1].trade_date,
    )


def test_atomic_recompute_idempotency_and_historical_correction(market):
    engine, service = market
    rows = data()
    collect(service, rows)
    before = snapshot(engine)
    assert len(before) == 65 and before[59]["ma60"] == Decimal("30.5000")
    collect(service, rows)
    assert snapshot(engine) == before
    correction = bar(day=rows[0].trade_date, close=Decimal("12"))
    collect(service, (correction,))
    after = snapshot(engine)
    assert after[4]["ma5"] == Decimal("5.2000")
    assert after[59]["ma60"] == Decimal("30.6833")
    assert after[60] == before[60]  # Historical correction no longer belongs to this window.


def test_indicator_failure_rolls_back_prices(market, monkeypatch):
    engine, service = market

    def fail(*args):
        raise sa.exc.SQLAlchemyError("fixture secret must not escape")

    monkeypatch.setattr("app.services.indicators.IndicatorRepository.upsert", fail)
    from app.core.errors import ApplicationError

    with pytest.raises(ApplicationError, match="Daily price storage unavailable"):
        collect(service, data())
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(DailyPrice)) == 0
    assert snapshot(engine) == []


@pytest.mark.anyio
async def test_real_query_contract_nulls_version_limits_status_and_errors(market):
    engine, service = market
    collect(service, data())
    with engine.begin() as conn:
        conn.execute(
            sa.insert(DataSyncJob),
            {
                "source": "fixture",
                "job_type": "incremental",
                "started_at": FETCHED,
                "finished_at": FETCHED,
                "status": "failed",
                "error_message": "password=fixture_private_value",
            },
        )
    app = create_app(
        Settings(app_env="test", test_database_url=engine.url.render_as_string(hide_password=False))
    )
    params = {"start_date": "2026-01-01", "end_date": "2026-04-30", "limit": 5}
    before = snapshot(engine)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", trust_env=False
        ) as client,
    ):
        path = "/api/v1/stocks/000001.SZ/indicators"
        response = await client.get(path, params=params)
        assert response.status_code == 200
        body = response.json()
        assert body["has_more"] and len(body["items"]) == 5
        assert body["items"][0]["ma5"] is None
        assert body["items"][4]["ma5"] == "3.0000"
        assert body["items"][4]["source"] == "mock_fixture"
        assert body["calculation_version"] == "sma-close-v1"
        assert (
            await client.get(path, params={**params, "calculation_version": "unknown"})
        ).status_code == 422
        assert (
            await client.get(path, params={**params, "end_date": "2025-01-01"})
        ).status_code == 422
        assert (await client.get(path, params={**params, "limit": 1001})).status_code == 422
        assert (
            await client.get(path.replace("000001", "000002"), params=params)
        ).status_code == 404
        empty = await client.get(
            path, params={"start_date": "2020-01-01", "end_date": "2020-01-02"}
        )
        assert empty.json()["items"] == []
        status = await client.get("/api/v1/system/data-status", params={"limit": 1})
        assert status.json()["items"][0]["error_code"] == "stored_error_redacted"
        assert "fixture_private_value" not in status.text
        assert status.json()["coverage_verified"] is False
    assert snapshot(engine) == before


def test_scheduler_real_locks_retries_partial_restart_and_incremental(market):
    from dataclasses import replace
    from datetime import UTC, datetime

    from app.collectors.errors import ProviderTimeoutError
    from app.core.errors import ApplicationError
    from app.jobs.collection import CollectionRunner, RetryPolicy
    from app.jobs.scheduler import AfterCloseScheduler, ReadyProvider, TradingCalendar
    from app.repositories.scheduling import ScheduleRepository
    from app.repositories.sync_jobs import SyncJobRepository
    from app.services.stocks import StockService

    engine, service = market
    days = frozenset({date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)})
    calendar = TradingCalendar("fixture_simulated", date(2026, 9, 1), date(2026, 10, 31), days)
    now = datetime(2026, 9, 29, 9, 30, tzinfo=UTC)
    with engine.begin() as conn:
        conn.execute(
            sa.insert(Stock),
            {"symbol": "000002.SZ", "name": "模拟失败股", "exchange": "SZ", "status": "listed"},
        )
    calls, delays = [], []

    class Provider:
        failures = 1

        def fetch_daily_prices(self, symbol, start, end):
            calls.append((symbol, start, end))
            if symbol == "000002.SZ":
                raise ProviderTimeoutError()
            if self.failures:
                self.failures -= 1
                return replace(
                    FixtureDailyProvider().fetch_daily_prices(symbol, start, end), source="akshare"
                )  # Not ready once.
            rows = (bar(day=end),)
            return replace(
                FixtureDailyProvider({symbol: rows}).fetch_daily_prices(symbol, start, end),
                source="akshare",
            )

    provider = Provider()
    sessions = create_session_factory(engine)
    runner = CollectionRunner(
        SyncJobRepository(engine),
        StockService(sessions),
        service,
        ReadyProvider(provider, calendar),
        retry=RetryPolicy(2, 0),
        sleep=delays.append,
    )
    repository = ScheduleRepository(engine)

    def build(symbols):
        return AfterCloseScheduler(repository, runner, calendar, symbols, date(2026, 9, 28))

    first = build(["000001.SZ", "000002.SZ"]).tick(now)
    assert first["status"] == "partial" and first["failed_jobs"] == 1
    assert len(delays) == 2 and len(calls) == 4
    with engine.connect() as conn:
        jobs = (
            conn.execute(sa.select(DataSyncJob.__table__).order_by(DataSyncJob.target_symbol))
            .mappings()
            .all()
        )
    assert [job["status"] for job in jobs] == ["succeeded", "failed"]
    assert jobs[0]["checkpoint_date"] == now.date()
    saved = snapshot(engine)
    # A newly created scheduler skips durable success after process restart.
    assert build(["000001.SZ"]).tick(now)["skipped_jobs"] == 1
    assert len(calls) == 4 and snapshot(engine) == saved
    retry = build(["000002.SZ"]).tick(now)
    assert retry["status"] == "failed"
    with engine.connect() as conn:
        assert (
            conn.scalar(sa.select(sa.func.count()).select_from(DataSyncJob)) == 2
        )  # Failed job ID reused.
    tomorrow = now.replace(day=30)
    assert build(["000001.SZ"]).tick(tomorrow)["status"] == "succeeded"
    assert calls[-1][1:] == (date(2026, 9, 29), date(2026, 9, 30))  # Overlap local watermark.
    other = ScheduleRepository(engine)
    with repository.ownership():
        with pytest.raises(ApplicationError, match="scheduler"):
            with other.ownership():
                pytest.fail("Duplicate scheduler acquired lock")
    with other.ownership():
        pass
    # CLI and scheduler also share existing collection ownership.
    with SyncJobRepository(engine).ownership():
        with pytest.raises(ApplicationError, match="collector"):
            build(["000002.SZ"]).tick(now)


def test_local_indicator_cli_rebuild_without_provider(market, monkeypatch, capsys):
    from app.jobs.cli import main

    engine, service = market
    collect(service, data())
    monkeypatch.setenv("TEST_DATABASE_URL", engine.url.render_as_string(hide_password=False))

    def forbidden(*args, **kwargs):
        raise AssertionError("Local indicator rebuild must not initialize provider")

    monkeypatch.setattr("app.jobs.cli.AkShareProvider", forbidden)
    before = snapshot(engine)
    assert main(["indicators", "--symbol", "000001.SZ"]) == 0
    assert '"changed_count": 0' in capsys.readouterr().out
    assert snapshot(engine) == before
    with engine.begin() as conn:
        conn.execute(sa.delete(TechnicalIndicator))
    assert main(["indicators", "--symbol", "000001.SZ"]) == 0
    assert '"changed_count": 65' in capsys.readouterr().out
    assert len(snapshot(engine)) == 65


def test_historical_insertion_updates_following_windows(market):
    engine, service = market
    rows = data()
    collect(service, rows[1:])
    assert snapshot(engine)[3]["ma5"] is None
    collect(service, rows[:1])
    from app.analysis.moving_averages import ClosePoint, calculate_moving_averages

    expected = calculate_moving_averages(
        ClosePoint(row.symbol, row.trade_date, row.close) for row in rows
    )
    assert [(row["ma5"], row["ma20"], row["ma60"]) for row in snapshot(engine)] == [
        (row.ma5, row.ma20, row.ma60) for row in expected
    ]


def test_concurrent_disjoint_appends_have_consistent_indicator_history(market):
    from concurrent.futures import ThreadPoolExecutor

    from app.analysis.moving_averages import ClosePoint, calculate_moving_averages

    engine, service = market
    rows = data()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(collect, service, part) for part in (rows[:30], rows[30:])]
        for future in futures:
            future.result(timeout=10)
    expected = calculate_moving_averages(
        ClosePoint(row.symbol, row.trade_date, row.close) for row in rows
    )
    assert [(row["ma5"], row["ma20"], row["ma60"]) for row in snapshot(engine)] == [
        (row.ma5, row.ma20, row.ma60) for row in expected
    ]


def test_actual_scheduler_cli_once_restart_and_safe_errors(market, tmp_path):
    import json
    import subprocess
    import sys

    engine, _ = market
    with engine.begin() as conn:
        conn.execute(
            sa.insert(Stock),
            {"symbol": "000002.SZ", "name": "模拟失败股", "exchange": "SZ", "status": "listed"},
        )
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests/fixtures/akshare/daily.json"
    (tmp_path / "akshare.py").write_text(f"""
from pathlib import Path
class Frame:
    columns=[]
    def to_dict(self, **kwargs): return __import__("json").loads(Path({str(fixture)!r}).read_text())
def stock_zh_a_hist(**kwargs):
    if kwargs['symbol']=='000002': raise KeyError('password=fixture_scheduler_private')
    return Frame()
""")
    (tmp_path / "requests").mkdir()
    (tmp_path / "requests/__init__.py").write_text("")
    (tmp_path / "requests/exceptions.py").write_text("class Timeout(Exception): pass\n")
    calendar = tmp_path / "calendar.json"
    calendar.write_text(
        json.dumps(
            {
                "source": "fixture_simulated",
                "coverage_start": "2026-09-01",
                "coverage_end": "2026-09-30",
                "trading_dates": ["2026-09-28", "2026-09-29"],
            }
        )
    )
    # Only the test harness injects a fixed clock; production CLI has no fake-data/clock switch.
    script = tmp_path / "run_scheduler.py"
    script.write_text("""
from datetime import datetime as RealClock, UTC
import app.jobs.scheduler as scheduler
class Clock(RealClock):
    @classmethod
    def now(cls, tz=None): return RealClock(2026,9,29,9,30,tzinfo=UTC).astimezone(tz)
scheduler.datetime = Clock
raise SystemExit(scheduler.main())
""")
    env = dict(
        os.environ,
        APP_ENV="test",
        TEST_DATABASE_URL=engine.url.render_as_string(hide_password=False),
        PYTHONPATH=os.pathsep.join([str(tmp_path), str(root)]),
    )
    args = [
        sys.executable,
        str(script),
        "--calendar",
        str(calendar),
        "--symbol",
        "000001.SZ",
        "--symbol",
        "000002.SZ",
        "--initial-start",
        "2026-09-28",
        "--retry-delay",
        "0",
        "--once",
    ]
    for index in range(2):
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "fixture_scheduler_private" not in result.stdout + result.stderr
        summary = json.loads(result.stdout.splitlines()[-1])
        assert summary["status"] == "partial" and summary["failed_jobs"] == 1
        assert summary["skipped_jobs"] == index
    assert len(snapshot(engine)) == 2
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(DataSyncJob)) == 2
