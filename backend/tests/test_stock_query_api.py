"""HTTP contracts with real query services and simulated repository results; no network."""

from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_stock_query_service
from app.collectors.provider import DailyBar, StockInfo
from app.repositories.daily_prices import DailyPriceRepository
from app.repositories.stocks import StockRepository
from app.services.stock_queries import StockQueryService

STOCK = StockInfo("000001.SZ", "模拟证券", "SZ")
START, END = date(2026, 9, 28), date(2026, 9, 29)
STAMP = datetime(2026, 9, 29, 10, tzinfo=UTC)
PARAMS = {"start_date": "2026-09-28", "end_date": "2026-09-29"}


def price(day=START, source="mock_fixture", stamp=STAMP):
    row = DailyBar(
        "000001.SZ",
        day,
        Decimal("10.0000"),
        Decimal("12.0000"),
        Decimal("9.0000"),
        Decimal("11.0000"),
        1200,
        Decimal("12345.67"),
    )
    return SimpleNamespace(**asdict(row), source=source, adjustment="none", fetched_at=stamp)


@pytest.fixture
def query_service(application, monkeypatch):
    factory = MagicMock()
    service = StockQueryService(factory)
    monkeypatch.setattr(
        StockRepository, "get", lambda self, symbol: STOCK if symbol == STOCK.symbol else None
    )
    monkeypatch.setattr(StockRepository, "exists", lambda self, symbol: symbol == STOCK.symbol)
    monkeypatch.setattr(StockRepository, "search", lambda self, query, page, size: ((STOCK,), 1))
    monkeypatch.setattr(DailyPriceRepository, "query", lambda self, *args: [price(), price(END)])
    application.dependency_overrides[get_stock_query_service] = lambda: service
    return service, factory


@pytest.mark.anyio
async def test_stock_list_and_detail_explicitly_unknown_provenance(client, query_service):
    response = await client.get("/api/v1/stocks")
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "symbol": STOCK.symbol,
                "name": "模拟证券",
                "exchange": "SZ",
                "list_date": None,
                "status": "unknown",
                "source": None,
                "fetched_at": None,
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }
    detail = await client.get("/api/v1/stocks/000001.sz")
    assert detail.status_code == 200 and detail.json() == response.json()["items"][0]


@pytest.mark.anyio
async def test_search_passes_bounded_literal_query_to_existing_service(
    client, query_service, monkeypatch
):
    calls = []

    def search(self, query, page, size):
        calls.append((query, page, size))
        return (), 42

    monkeypatch.setattr(StockRepository, "search", search)
    response = await client.get(
        "/api/v1/stocks", params={"query": " %_ ", "page": 2, "page_size": 1}
    )
    assert response.json() == {"items": [], "total": 42, "page": 2, "page_size": 1}
    assert calls == [("%_", 2, 1)]


@pytest.mark.anyio
async def test_prices_exact_strings_units_per_row_provenance_and_limit(client, query_service):
    response = await client.get("/api/v1/stocks/000001.SZ/prices", params={**PARAMS, "limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert (
        body["symbol"],
        body["start_date"],
        body["end_date"],
        body["limit"],
        body["has_more"],
    ) == ("000001.SZ", "2026-09-28", "2026-09-29", 1, True)
    assert (body["price_unit"], body["volume_unit"], body["amount_unit"], body["adjustment"]) == (
        "CNY",
        "share",
        "CNY",
        "none",
    )
    assert body["items"] == [
        {
            "symbol": "000001.SZ",
            "trade_date": "2026-09-28",
            "open": "10.0000",
            "high": "12.0000",
            "low": "9.0000",
            "close": "11.0000",
            "volume_shares": 1200,
            "amount_cny": "12345.67",
            "source": "mock_fixture",
            "adjustment": "none",
            "fetched_at": "2026-09-29T10:00:00Z",
        }
    ]


@pytest.mark.anyio
async def test_empty_prices_differ_from_missing_stock(client, query_service, monkeypatch):
    monkeypatch.setattr(DailyPriceRepository, "query", lambda self, *args: [])
    response = await client.get("/api/v1/stocks/000001.SZ/prices", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["items"] == [] and response.json()["has_more"] is False
    for suffix in ("", "/prices"):
        missing = await client.get("/api/v1/stocks/600519.SH" + suffix, params=PARAMS)
        assert missing.status_code == 404 and missing.json()["code"] == "stock_not_found"
        assert missing.json()["request_id"] == missing.headers["X-Request-ID"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path,params",
    [
        ("/stocks", {"page": 0}),
        ("/stocks", {"page_size": 101}),
        ("/stocks", {"page_size": 0}),
        ("/stocks", {"page": "true"}),
        ("/stocks", {"query": "x" * 129}),
        ("/stocks", {"query": "\x00"}),
        ("/stocks", {"page": 2**64}),
        ("/stocks/invalid", {}),
        ("/stocks/000001.SH", {}),
        ("/stocks/920001.BJ", {}),
        ("/stocks/000001.SZ/prices", {}),
        ("/stocks/000001.SZ/prices", {**PARAMS, "start_date": "bad"}),
        ("/stocks/000001.SZ/prices", {**PARAMS, "end_date": "2026-09-27"}),
        ("/stocks/000001.SZ/prices", {**PARAMS, "limit": 0}),
        ("/stocks/000001.SZ/prices", {**PARAMS, "limit": 1001}),
    ],
)
async def test_invalid_queries_fail_before_database(client, query_service, path, params):
    response = await client.get("/api/v1" + path, params=params)
    assert response.status_code == 422
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    query_service[1].assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path,params",
    [
        ("/stocks", {}),
        ("/stocks/000001.SZ", {}),
        ("/stocks/000001.SZ/prices", PARAMS),
    ],
)
async def test_storage_failures_are_safe_and_not_empty_success(
    client, query_service, path, params, capsys
):
    query_service[1].side_effect = SQLAlchemyError(
        "postgresql://secret:fixture-db-secret@localhost/db"
    )
    response = await client.get("/api/v1" + path, params=params)
    assert response.status_code == 503
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert "fixture-db-secret" not in response.text + capsys.readouterr().out


@pytest.mark.anyio
async def test_missing_database_config_safe_and_health_independent(client, application):
    response = await client.get("/api/v1/stocks")
    assert response.status_code == 503 and response.json()["code"] == "stock_query_unavailable"
    assert (await client.get("/api/v1/health")).json() == {"status": "ok", "version": "0.1.0"}
    assert application.state.query_database.engine is None


@pytest.mark.anyio
async def test_openapi_read_only_routes_required_dates_and_decimal_contract(client):
    document = (await client.get("/openapi.json")).json()
    assert set(document["paths"]) == {
        "/api/v1/health",
        "/api/v1/stocks",
        "/api/v1/stocks/{symbol}",
        "/api/v1/stocks/{symbol}/prices",
        "/api/v1/stocks/{symbol}/indicators",
        "/api/v1/system/data-status",
    }
    assert all(set(item) == {"get"} for item in document["paths"].values())
    params = document["paths"]["/api/v1/stocks/{symbol}/prices"]["get"]["parameters"]
    assert {p["name"] for p in params if p["required"]} == {"symbol", "start_date", "end_date"}
    schema = document["components"]["schemas"]["DailyPriceResponse"]["properties"]
    assert schema["close"]["type"] == "string"


@pytest.mark.parametrize(
    "method,args,kwargs",
    [
        ("detail", ("bad",), {}),
        ("prices", ("000001.SZ", END, START), {}),
        ("prices", ("000001.SZ", START, END), {"limit": True}),
    ],
)
def test_service_prechecks_without_http(method, args, kwargs):
    from app.core.errors import ApplicationError

    factory = MagicMock()
    with pytest.raises(ApplicationError):
        getattr(StockQueryService(factory), method)(*args, **kwargs)
    factory.assert_not_called()


@pytest.mark.anyio
async def test_engine_reused_and_disposed_at_lifespan_end(application, monkeypatch):
    from app.api import dependencies

    engine = MagicMock()
    create = MagicMock(return_value=engine)
    monkeypatch.setattr(dependencies, "create_configured_database_engine", create)
    monkeypatch.setattr(dependencies, "create_session_factory", lambda value: MagicMock())
    async with application.router.lifespan_context(application):
        create.assert_not_called()
        application.state.query_database.session()
        application.state.query_database.session()
        create.assert_called_once()
        engine.execution_options.assert_called_once_with(postgresql_readonly=True)
    engine.dispose.assert_called_once()
