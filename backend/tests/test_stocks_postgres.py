"""Real PostgreSQL tests; data are simulated and restricted to a new isolated database."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from alembic import command
from app.collectors.provider import StockInfo
from app.core.database import create_session_factory
from app.core.errors import ApplicationError
from app.models import Stock
from app.services.stocks import StockService
from tests.test_stock_service import FixtureProvider

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def stock_engine():
    value = os.getenv("STOCK_TEST_DATABASE_URL")
    if not value:
        pytest.skip("STOCK_TEST_DATABASE_URL requires a new empty *_stocks_test database")
    url = make_url(value)
    assert url.drivername == "postgresql+psycopg" and (url.database or "").endswith("_stocks_test")
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
def service(stock_engine):
    # Only the newly-created, suffix-guarded fixture database is ever cleaned up.
    assert sa.inspect(stock_engine).get_table_names()
    yield StockService(create_session_factory(stock_engine))
    with stock_engine.begin() as connection:
        connection.execute(sa.delete(Stock))


def test_insert_repeated_sync_and_committed_search(service, stock_engine):
    row = StockInfo(" 000001.sz ", " 测试证券 ", "SZ")
    result = service.sync(FixtureProvider((row,)))
    assert (result.processed_count, result.changed_count) == (1, 1)
    assert service.sync(FixtureProvider((row,))).changed_count == 0
    with stock_engine.connect() as connection:
        persisted = connection.execute(sa.select(Stock.__table__)).mappings().one()
        assert persisted["name"] == "测试证券" and persisted["symbol"] == "000001.SZ"
        assert persisted["status"] == "unknown" and persisted["list_date"] is None
    assert service.search("000001").items == (replace(row, symbol="000001.SZ", name="测试证券"),)


def test_merge_preserves_known_fields_and_absent_securities(service):
    known = StockInfo("000001.SZ", "测试旧名", "SZ", date(2000, 1, 1), "listed")
    absent = StockInfo("600519.SH", "测试缺席", "SH", status="delisted")
    service.sync(FixtureProvider((known, absent)))
    service.sync(
        FixtureProvider((replace(known, name="测试新名", list_date=None, status="unknown"),))
    )
    assert service.search("000001").items == (replace(known, name="测试新名"),)
    assert service.search("600519").items == (absent,)
    assert service.sync(FixtureProvider()).processed_count == 0
    assert service.search().total == 2
    confirmed = replace(known, list_date=date(2001, 1, 1), status="suspended")
    assert service.sync(FixtureProvider((confirmed,))).changed_count == 1
    assert service.search("000001").items == (confirmed,)


def test_search_literal_case_insensitive_and_pagination(service):
    rows = (
        StockInfo("600519.SH", "测试alpha_证券", "SH"),
        StockInfo("000002.SZ", "测试%证券", "SZ"),
        StockInfo("000001.SZ", "测试/证券", "SZ"),
        StockInfo("000003.SZ", "测试普通证券", "SZ"),
    )
    service.sync(FixtureProvider(rows))
    assert service.search(" ALPHA ").items == (rows[0],)
    assert service.search("sh").items == (rows[0],)
    assert service.search("_").items == (rows[0],)
    assert service.search("%").items == (rows[1],)
    assert service.search("/").items == (rows[2],)
    assert service.search("' OR 1=1 --").total == 0
    first, second = service.search("测试", page_size=2), service.search("测试", page=2, page_size=2)
    assert first.total == second.total == 4
    assert [row.symbol for row in first.items + second.items] == sorted(row.symbol for row in rows)
    assert service.search(page=3, page_size=2).items == ()
    assert service.search("不存在").total == 0


def test_multi_chunk_failure_rolls_back_entire_snapshot(service, stock_engine):
    rows = tuple(StockInfo(f"{code:06}.SZ", "测试批次证券", "SZ") for code in range(1, 503))
    inserts = 0

    def fail_second_insert(connection, cursor, statement, parameters, context, executemany):
        nonlocal inserts
        if statement.startswith("INSERT INTO stocks"):
            inserts += 1
            if inserts == 2:
                raise SQLAlchemyError("password=fixture-batch-secret")

    sa.event.listen(stock_engine, "before_cursor_execute", fail_second_insert)
    try:
        with pytest.raises(ApplicationError) as error:
            service.sync(FixtureProvider(rows))
        assert error.value.code == "stock_storage_error" and inserts == 2
    finally:
        sa.event.remove(stock_engine, "before_cursor_execute", fail_second_insert)
    assert service.search().total == 0
    assert service.sync(FixtureProvider(rows)).changed_count == 502
    assert service.search().total == 502


def test_concurrent_identical_sync_is_idempotent(service):
    provider = FixtureProvider((StockInfo("000001.SZ", "测试并发证券", "SZ"),))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: service.sync(provider), range(2)))
    assert sum(result.changed_count for result in results) == 1
    assert service.search().total == 1


def test_search_count_and_items_share_a_snapshot(service, stock_engine):
    service.sync(FixtureProvider((StockInfo("000001.SZ", "测试初始证券", "SZ"),)))
    injected = False

    def insert_after_count(connection, cursor, statement, parameters, context, executemany):
        nonlocal injected
        if statement.startswith("SELECT count(") and not injected:
            injected = True
            with stock_engine.begin() as concurrent:
                concurrent.execute(
                    sa.insert(Stock),
                    {
                        "symbol": "600519.SH",
                        "name": "测试并发新增",
                        "exchange": "SH",
                        "status": "unknown",
                    },
                )

    sa.event.listen(stock_engine, "after_cursor_execute", insert_after_count)
    try:
        result = service.search()
        assert injected and result.total == 1
        assert [row.symbol for row in result.items] == ["000001.SZ"]
    finally:
        sa.event.remove(stock_engine, "after_cursor_execute", insert_after_count)
    assert service.search().total == 2
