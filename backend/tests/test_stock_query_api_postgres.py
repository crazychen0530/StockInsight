"""Full Router -> Service -> Repository -> PostgreSQL with explicitly simulated rows."""

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import Settings
from app.main import create_app
from app.models import DailyPrice, Stock

pytestmark = [pytest.mark.postgres, pytest.mark.anyio]
STAMP = datetime(2026, 10, 1, 10, tzinfo=UTC)
PARAMS = {"start_date": "2026-09-28", "end_date": "2026-09-30"}


@pytest.fixture(scope="module")
def query_engine():
    value = os.getenv("QUERY_API_TEST_DATABASE_URL")
    if not value:
        pytest.skip("QUERY_API_TEST_DATABASE_URL requires a new empty *_query_api_test database")
    url = make_url(value)
    assert url.drivername == "postgresql+psycopg" and (url.database or "").endswith(
        "_query_api_test"
    )
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


def quote(symbol="000001.SZ", day=date(2026, 9, 28), **changes):
    return {
        "symbol": symbol,
        "trade_date": day,
        "open": Decimal("10.1234"),
        "high": Decimal("12"),
        "low": Decimal("9"),
        "close": Decimal("11.4321"),
        "volume_shares": 1200,
        "amount_cny": Decimal("9999999999999999999999.99"),
        "source": "mock_fixture",
        "adjustment": "none",
        "fetched_at": STAMP,
        **changes,
    }


@pytest.fixture
async def api(query_engine, monkeypatch):
    # Fixture setup is the only write path; the HTTP application uses a read-only engine.
    with query_engine.begin() as conn:
        conn.execute(
            sa.insert(Stock),
            [
                {
                    "symbol": "000001.SZ",
                    "name": "模拟alpha_证券",
                    "exchange": "SZ",
                    "status": "unknown",
                },
                {"symbol": "000002.SZ", "name": "模拟%证券", "exchange": "SZ", "status": "listed"},
                {
                    "symbol": "600519.SH",
                    "name": "模拟其他证券",
                    "exchange": "SH",
                    "status": "delisted",
                },
            ],
        )
        conn.execute(
            sa.insert(DailyPrice),
            [
                quote(day=date(2026, 9, 30), source="mock_fixture_second"),
                quote(),
                quote(day=date(2026, 9, 29)),
                quote("600519.SH"),
            ],
        )
    from app.collectors.akshare import AkShareProvider

    def forbidden(*args, **kwargs):
        raise AssertionError("Query must never invoke a provider")

    monkeypatch.setattr(AkShareProvider, "fetch_stocks", forbidden)
    monkeypatch.setattr(AkShareProvider, "fetch_daily_prices", forbidden)
    application = create_app(
        Settings(
            app_env="test", test_database_url=query_engine.url.render_as_string(hide_password=False)
        )
    )
    try:
        async with application.router.lifespan_context(application):
            async with AsyncClient(
                transport=ASGITransport(app=application),
                base_url="http://testserver",
                trust_env=False,
            ) as client:
                yield client, application
    finally:
        with query_engine.begin() as conn:
            conn.execute(sa.delete(DailyPrice))
            conn.execute(sa.delete(Stock))


async def test_search_pagination_literal_matching_and_metadata(api):
    client, app = api
    first = (await client.get("/api/v1/stocks", params={"page_size": 2})).json()
    second = (await client.get("/api/v1/stocks", params={"page_size": 2, "page": 2})).json()
    assert first["total"] == second["total"] == 3
    assert [r["symbol"] for r in first["items"] + second["items"]] == [
        "000001.SZ",
        "000002.SZ",
        "600519.SH",
    ]
    assert all(r["source"] is None and r["fetched_at"] is None for r in first["items"])
    for query, expected in (("_", 1), ("%", 1), ("ALPHA", 1), ("' OR 1=1 --", 0), ("000001", 1)):
        response = await client.get("/api/v1/stocks", params={"query": query})
        assert response.status_code == 200 and response.json()["total"] == expected
    assert (await client.get("/api/v1/stocks", params={"page": 4})).json()["items"] == []
    with app.state.query_database.factory() as session:
        assert session.scalar(sa.text("SHOW transaction_read_only")) == "on"


async def test_detail_existing_missing_and_empty_prices(api):
    client, _ = api
    assert (await client.get("/api/v1/stocks/000001.sz")).json()["status"] == "unknown"
    assert (await client.get("/api/v1/stocks/600519.SH")).json()["status"] == "delisted"
    for suffix in ("", "/prices"):
        missing = await client.get("/api/v1/stocks/000003.SZ" + suffix, params=PARAMS)
        assert missing.status_code == 404
    empty = await client.get("/api/v1/stocks/000002.SZ/prices", params=PARAMS)
    assert empty.status_code == 200 and empty.json()["items"] == []
    absent_range = await client.get(
        "/api/v1/stocks/000001.SZ/prices",
        params={"start_date": "2020-01-01", "end_date": "2020-01-02"},
    )
    assert absent_range.status_code == 200 and absent_range.json()["items"] == []


async def test_prices_closed_interval_sorted_limit_and_exact_metadata(api):
    client, _ = api
    body = (
        await client.get("/api/v1/stocks/000001.SZ/prices", params={**PARAMS, "limit": 2})
    ).json()
    assert [r["trade_date"] for r in body["items"]] == ["2026-09-28", "2026-09-29"]
    assert body["has_more"] is True and len(body["items"]) == 2
    row = body["items"][0]
    assert row["close"] == "11.4321" and row["amount_cny"] == "9999999999999999999999.99"
    assert row["volume_shares"] == 1200 and row["source"] == "mock_fixture"
    assert row["fetched_at"] == "2026-10-01T10:00:00Z" and row["adjustment"] == "none"
    all_rows = (await client.get("/api/v1/stocks/000001.SZ/prices", params=PARAMS)).json()
    assert all_rows["has_more"] is False and len(all_rows["items"]) == 3
    assert all_rows["items"][-1]["source"] == "mock_fixture_second"
    single = (
        await client.get(
            "/api/v1/stocks/000001.SZ/prices",
            params={"start_date": "2026-09-29", "end_date": "2026-09-29"},
        )
    ).json()
    assert [r["trade_date"] for r in single["items"]] == ["2026-09-29"]


async def test_queries_do_not_mutate_persisted_rows(api, query_engine):
    client, _ = api

    def snapshot():
        with query_engine.connect() as conn:
            return conn.execute(
                sa.select(DailyPrice.__table__).order_by(DailyPrice.symbol, DailyPrice.trade_date)
            ).all()

    before = snapshot()
    for _ in range(2):
        await client.get("/api/v1/stocks")
        await client.get("/api/v1/stocks/000001.SZ")
        await client.get("/api/v1/stocks/000001.SZ/prices", params=PARAMS)
    assert snapshot() == before


async def test_price_existence_and_rows_share_snapshot(api, query_engine):
    client, app = api
    await client.get("/api/v1/stocks")  # Initialize the API-owned engine.
    injected = False

    def insert_after_exists(conn, cursor, statement, parameters, context, executemany):
        nonlocal injected
        if statement.startswith("SELECT stocks.symbol") and not injected:
            injected = True
            with query_engine.begin() as other:
                other.execute(sa.insert(DailyPrice), quote("000002.SZ"))

    engine = app.state.query_database.engine
    sa.event.listen(engine, "after_cursor_execute", insert_after_exists)
    try:
        first = await client.get("/api/v1/stocks/000002.SZ/prices", params=PARAMS)
        assert injected and first.json()["items"] == []
    finally:
        sa.event.remove(engine, "after_cursor_execute", insert_after_exists)
    second = await client.get("/api/v1/stocks/000002.SZ/prices", params=PARAMS)
    assert len(second.json()["items"]) == 1
