"""Real PostgreSQL transactions with simulated quotes in a new isolated database."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from alembic import command
from app.collectors.provider import StockInfo
from app.collectors.validator import MarketDataValidationError
from app.core.database import create_session_factory
from app.core.errors import ApplicationError
from app.models import DailyPrice, Stock, TechnicalIndicator
from app.services.daily_prices import DailyPriceService
from app.services.stocks import StockService
from tests.test_daily_price_service import END, FETCHED, START, FixtureDailyProvider, bar
from tests.test_stock_service import FixtureProvider

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def price_engine():
    value = os.getenv("DAILY_PRICE_TEST_DATABASE_URL")
    if not value:
        pytest.skip("DAILY_PRICE_TEST_DATABASE_URL requires a new empty *_prices_test database")
    url = make_url(value)
    assert url.drivername == "postgresql+psycopg" and (url.database or "").endswith("_prices_test")
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
def price_service(price_engine):
    factory = create_session_factory(price_engine)
    StockService(factory).sync(
        FixtureProvider(
            tuple(
                StockInfo(symbol, "测试日线证券", symbol[-2:])
                for symbol in ("000001.SZ", "000002.SZ", "600519.SH")
            )
        )
    )
    yield DailyPriceService(factory)
    # Only this module's suffix-guarded fresh test database is cleaned.
    with price_engine.begin() as connection:
        connection.execute(sa.delete(TechnicalIndicator))
        connection.execute(sa.delete(DailyPrice))
        connection.execute(sa.delete(Stock))


def rows(engine):
    with engine.connect() as connection:
        return (
            connection.execute(
                sa.select(DailyPrice.__table__).order_by(DailyPrice.symbol, DailyPrice.trade_date)
            )
            .mappings()
            .all()
        )


def test_committed_prices_exact_metadata_and_idempotency(price_service, price_engine):
    provider = FixtureDailyProvider({"000001.SZ": (bar(day=END), bar())})
    first = price_service.sync(provider, "000001.SZ", START, END)
    assert (first.processed_count, first.changed_count) == (2, 2)
    persisted = rows(price_engine)
    assert persisted[0]["open"] == Decimal("10.0000")
    assert persisted[0]["volume_shares"] == 1200
    assert persisted[0]["amount_cny"] == Decimal("12345.67")
    assert persisted[0]["source"] == "mock_fixture" and persisted[0]["adjustment"] == "none"
    assert persisted[0]["fetched_at"] == FETCHED
    assert price_service.sync(provider, "000001.SZ", START, END).changed_count == 0
    newer = FixtureDailyProvider(provider.data, FETCHED + timedelta(hours=1))
    assert price_service.sync(newer, "000001.SZ", START, END).changed_count == 0
    assert rows(price_engine) == persisted  # Timestamp-only retries never rewrite the row.


def test_corrections_update_values_and_receipt_together(price_service, price_engine):
    price_service.sync(FixtureDailyProvider({"000001.SZ": (bar(),)}), "000001.SZ", START, END)
    revised = bar(close=Decimal("10.5"), volume_shares=1300, amount_cny=Decimal("13000.10"))
    stamp = FETCHED + timedelta(hours=1)
    result = price_service.sync(
        FixtureDailyProvider({"000001.SZ": (revised,)}, stamp), "000001.SZ", START, END
    )
    assert result.changed_count == 1
    persisted = rows(price_engine)
    assert len(persisted) == 1 and persisted[0]["close"] == Decimal("10.5")
    assert persisted[0]["fetched_at"] == stamp and persisted[0]["volume_shares"] == 1300


def test_inclusive_interval_backfill_preserves_other_dates(price_service, price_engine):
    later = date(2026, 9, 30)
    price_service.sync(
        FixtureDailyProvider({"000001.SZ": (bar(day=later),)}), "000001.SZ", later, later
    )
    provider = FixtureDailyProvider({"000001.SZ": (bar(), bar(day=END))})
    result = price_service.sync(provider, "000001.SZ", START, END, trading_dates={START, END})
    assert provider.calls == [("000001.SZ", START, END)] and result.changed_count == 2
    assert [row["trade_date"] for row in rows(price_engine)] == [START, END, later]
    empty = price_service.sync(FixtureDailyProvider(), "000001.SZ", START, END)
    assert empty.processed_count == 0 and len(rows(price_engine)) == 3


@pytest.mark.parametrize(
    "bad_rows",
    [
        (bar(), bar()),
        (bar(), bar(day=date(2026, 9, 30))),
        (bar(), bar(day=END, close=Decimal("99"))),
    ],
)
def test_whole_security_validation_preserves_existing_data(price_service, price_engine, bad_rows):
    price_service.sync(FixtureDailyProvider({"000001.SZ": (bar(),)}), "000001.SZ", START, END)
    original = rows(price_engine)
    with pytest.raises(MarketDataValidationError):
        price_service.sync(FixtureDailyProvider({"000001.SZ": bad_rows}), "000001.SZ", START, END)
    assert rows(price_engine) == original


def test_unknown_stock_partial_failure_and_manual_recovery(price_service, price_engine):
    symbols = ("000001.SZ", "000003.SZ", "600519.SH")
    provider = FixtureDailyProvider({symbol: (bar(symbol),) for symbol in symbols})
    result = price_service.sync_many(provider, symbols, START, END)
    assert (result.status, result.success_count, result.failure_count) == ("partial", 2, 1)
    assert result.results[1].code == "daily_stock_missing"
    assert [row["symbol"] for row in rows(price_engine)] == ["000001.SZ", "600519.SH"]
    StockService(create_session_factory(price_engine)).sync(
        FixtureProvider((StockInfo("000003.SZ", "测试补同步", "SZ"),))
    )
    recovered = price_service.sync_many(provider, symbols, START, END)
    assert recovered.status == "succeeded"
    assert [row.changed_count for row in recovered.results] == [0, 1, 0]
    assert len(rows(price_engine)) == 3


def test_multichunk_failure_rolls_back_updates_and_new_rows(price_service, price_engine):
    start, end = date(2023, 1, 2), date(2025, 1, 31)
    days = []
    day = start
    while len(days) < 502:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    original = bar(day=start)
    price_service.sync(FixtureDailyProvider({"000001.SZ": (original,)}), "000001.SZ", start, end)
    before = rows(price_engine)
    provider = FixtureDailyProvider(
        {"000001.SZ": tuple(bar(day=day, close=Decimal("10.5")) for day in days)}
    )
    inserts = 0

    def fail_second(connection, cursor, statement, parameters, context, executemany):
        nonlocal inserts
        if statement.startswith("INSERT INTO daily_prices"):
            inserts += 1
            if inserts == 2:
                raise SQLAlchemyError("password=fixture-daily-chunk-secret")

    sa.event.listen(price_engine, "before_cursor_execute", fail_second)
    try:
        with pytest.raises(ApplicationError) as failure:
            price_service.sync(provider, "000001.SZ", start, end)
        assert failure.value.code == "daily_price_storage_error" and inserts == 2
    finally:
        sa.event.remove(price_engine, "before_cursor_execute", fail_second)
    assert rows(price_engine) == before
    assert price_service.sync(provider, "000001.SZ", start, end).changed_count == 502
    assert len(rows(price_engine)) == 502
    assert price_service.sync(provider, "000001.SZ", start, end).changed_count == 0


def test_database_failure_does_not_rollback_other_securities(price_service, price_engine):
    symbols = ("000001.SZ", "000002.SZ", "600519.SH")
    provider = FixtureDailyProvider({symbol: (bar(symbol),) for symbol in symbols})
    inserts = 0

    def fail_middle(connection, cursor, statement, parameters, context, executemany):
        nonlocal inserts
        if statement.startswith("INSERT INTO daily_prices"):
            inserts += 1
            if inserts == 2:
                raise SQLAlchemyError("password=fixture-daily-middle-secret")

    sa.event.listen(price_engine, "before_cursor_execute", fail_middle)
    try:
        result = price_service.sync_many(provider, symbols, START, END)
    finally:
        sa.event.remove(price_engine, "before_cursor_execute", fail_middle)
    assert (result.status, result.success_count, result.failure_count) == ("partial", 2, 1)
    assert result.results[1].code == "daily_price_storage_error"
    assert [row["symbol"] for row in rows(price_engine)] == [symbols[0], symbols[2]]
    recovered = price_service.sync_many(provider, symbols, START, END)
    assert [row.changed_count for row in recovered.results] == [0, 1, 0]


def test_concurrent_identical_upsert_is_idempotent(price_service, price_engine):
    provider = FixtureDailyProvider({"000001.SZ": (bar(), bar(day=END))})
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda _: price_service.sync(provider, "000001.SZ", START, END), range(2))
        )
    assert sum(row.changed_count for row in results) == 2
    assert len(rows(price_engine)) == 2


def test_real_commit_failure_returns_no_success_and_rolls_back(price_service, price_engine):
    def fail_commit(connection):
        raise SQLAlchemyError("password=fixture-daily-commit-secret")

    sa.event.listen(price_engine, "commit", fail_commit)
    try:
        with pytest.raises(ApplicationError) as failure:
            price_service.sync(
                FixtureDailyProvider({"000001.SZ": (bar(),)}), "000001.SZ", START, END
            )
        assert failure.value.code == "daily_price_storage_error"
    finally:
        sa.event.remove(price_engine, "commit", fail_commit)
    assert rows(price_engine) == []


def test_schema_decimal_limits_and_zero_volume_remain_exact(price_service, price_engine):
    value = Decimal("99999999999999.9999")
    row = replace(
        bar(),
        open=value,
        high=value,
        low=value,
        close=value,
        amount_cny=Decimal("9999999999999999999999.99"),
        volume_shares=2**63 - 1,
    )
    price_service.sync(
        FixtureDailyProvider(
            {"000001.SZ": (row, bar(day=END, volume_shares=0, amount_cny=Decimal("0")))}
        ),
        "000001.SZ",
        START,
        END,
    )
    stored = rows(price_engine)
    assert stored[0]["open"] == value and stored[0]["amount_cny"] == row.amount_cny
    assert stored[0]["volume_shares"] == 2**63 - 1
    assert stored[1]["volume_shares"] == 0 and stored[1]["amount_cny"] == 0
