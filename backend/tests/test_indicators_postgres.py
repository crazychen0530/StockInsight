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
