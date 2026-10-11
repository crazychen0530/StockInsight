"""Offline provider contracts: every market value here is explicitly simulated."""

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.collectors.akshare import AkShareProvider
from app.collectors.errors import ProviderContractError, ProviderError, ProviderTimeoutError
from app.collectors.provider import DailyBar, MarketDataBatch, MarketDataProvider, StockInfo
from app.core.config import ConfigurationError, Settings, load_settings

FIXTURES = Path(__file__).parent / "fixtures" / "akshare"
START, END = date(2026, 9, 28), date(2026, 9, 29)


class FixtureTransport:
    def __init__(self, payload: str | Exception):
        self.payload = payload
        self.calls = []

    def call(self, interface, parameters, timeout):
        self.calls.append((interface, parameters, timeout))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class MockProvider:
    """Alternative provider with no AKShare, database, or network dependency."""

    def fetch_stocks(self):
        return MarketDataBatch(
            (StockInfo("000001.SZ", "模拟证券", "SZ"),),
            "mock_fixture",
            "fixture",
            datetime.now(UTC),
        )

    def fetch_daily_prices(self, symbol, start_date, end_date):
        return MarketDataBatch(
            (DailyBar(symbol, start_date, *(Decimal("1") for _ in range(4)), 100, Decimal("100")),),
            "mock_fixture",
            "fixture",
            datetime.now(UTC),
        )


def provider(payload):
    return AkShareProvider(Settings(app_env="test"), transport=FixtureTransport(payload))


def test_stocks_mapping_scope_unknown_fields_and_metadata():
    result = provider((FIXTURES / "stocks.json").read_text()).fetch_stocks()
    assert [row.symbol for row in result.records] == [
        "000001.SZ",
        "600519.SH",
        "688001.SH",
        "300001.SZ",
    ]
    assert all(row.status == "unknown" and row.list_date is None for row in result.records)
    assert result.source == "akshare" and result.source_interface == "stock_info_a_code_name"
    assert result.fetched_at.tzinfo is UTC
    assert not hasattr(result.records[0], "code")
    with pytest.raises(FrozenInstanceError):
        result.records[0].name = "changed"


def test_daily_mapping_decimal_units_and_exact_request():
    transport = FixtureTransport((FIXTURES / "daily.json").read_text())
    instance = AkShareProvider(Settings(market_data_timeout_seconds=7), transport=transport)
    before = datetime.now(UTC)
    result = instance.fetch_daily_prices("000001.SZ", START, END)
    assert before <= result.fetched_at <= datetime.now(UTC)
    row = result.records[0]
    assert row == DailyBar(
        "000001.SZ",
        START,
        Decimal("10.10"),
        Decimal("10.50"),
        Decimal("9.80"),
        Decimal("10.25"),
        1200,
        Decimal("12345.67"),
    )
    assert result.records[1].volume_shares == 0
    assert (result.adjustment, result.price_unit, result.volume_unit, result.amount_unit) == (
        "none",
        "CNY",
        "share",
        "CNY",
    )
    assert transport.calls == [
        (
            "stock_zh_a_hist",
            {
                "symbol": "000001",
                "period": "daily",
                "start_date": "20260928",
                "end_date": "20260929",
                "adjust": "",
                "timeout": 7,
            },
            7,
        )
    ]


@pytest.mark.parametrize(
    "instance", [MockProvider(), provider((FIXTURES / "stocks.json").read_text())]
)
def test_replaceable_stock_contract(instance: MarketDataProvider):
    assert isinstance(instance, MarketDataProvider)
    assert all(isinstance(row, StockInfo) for row in instance.fetch_stocks().records)


@pytest.mark.parametrize(
    "instance", [MockProvider(), provider((FIXTURES / "daily.json").read_text())]
)
def test_replaceable_daily_contract(instance: MarketDataProvider):
    result = instance.fetch_daily_prices("000001.SZ", START, END)
    assert all(isinstance(row, DailyBar) for row in result.records)
    assert all(isinstance(row.close, Decimal) for row in result.records)


@pytest.mark.parametrize("method", ["stocks", "daily"])
@pytest.mark.parametrize("with_columns", [True, False])
def test_empty_results_preserve_metadata(method, with_columns):
    table = json.loads((FIXTURES / f"{method}.json").read_text())
    table["data"] = []
    if not with_columns:
        table["columns"] = []
    instance = provider(json.dumps(table))
    result = (
        instance.fetch_stocks()
        if method == "stocks"
        else instance.fetch_daily_prices("000001.SZ", START, END)
    )
    assert result.records == ()
    assert result.source == "akshare" and result.fetched_at.tzinfo is UTC


@pytest.mark.parametrize("method", ["stocks", "daily"])
def test_timeout_is_not_an_empty_success(method, capsys):
    instance = provider(ProviderTimeoutError())
    with pytest.raises(ProviderTimeoutError) as failure:
        if method == "stocks":
            instance.fetch_stocks()
        else:
            instance.fetch_daily_prices("000001.SZ", START, END)
    assert failure.value.retryable and failure.value.code == "provider_timeout"
    output = capsys.readouterr().out
    assert "provider_timeout" in output


@pytest.mark.parametrize(
    "payload",
    [
        "not JSON password=fixture-secret",
        "{}",
        "null",
        '{"columns":["code"],"data":[]}',
        '{"columns":["code","name","name"],"data":[]}',
        '{"columns":["code","name"],"data":[["000001"]]}',
        '{"columns":["code","name"],"data":[[1,"模拟"]]}',
        '{"columns":["code","name"],"data":[["700001","模拟"]]}',
        '{"columns":["code","name"],"data":[["000001",null]]}',
    ],
)
def test_stock_field_drift_is_safe(payload, capsys):
    with pytest.raises(ProviderContractError) as failure:
        provider(payload).fetch_stocks()
    assert not failure.value.retryable
    assert "fixture-secret" not in str(failure.value) + capsys.readouterr().out


@pytest.mark.parametrize(
    "column,value",
    [
        ("股票代码", "600519"),
        ("日期", "2026-09-30"),
        ("日期", "invalid"),
        ("收盘", None),
        ("开盘", "NaN"),
        ("成交量", "Infinity"),
        ("成交量", "1.001"),
        ("成交额", True),
    ],
)
def test_daily_unrepresentable_or_uncorrelated_rows_fail(column, value):
    table = json.loads((FIXTURES / "daily.json").read_text())
    table["data"][0][table["columns"].index(column)] = value
    with pytest.raises(ProviderContractError):
        provider(json.dumps(table)).fetch_daily_prices("000001.SZ", START, END)


def test_daily_missing_field_fails_even_when_empty():
    table = json.loads((FIXTURES / "daily.json").read_text())
    table["columns"].remove("成交量")
    table["data"] = []
    with pytest.raises(ProviderContractError):
        provider(json.dumps(table)).fetch_daily_prices("000001.SZ", START, END)


@pytest.mark.parametrize(
    "symbol,start,end",
    [
        ("000001", START, END),
        ("000001.SH", START, END),
        ("920001.BJ", START, END),
        ("700001.SH", START, END),
        ("000001.SZ", END, START),
        ("000001.SZ", "20260928", END),
    ],
)
def test_invalid_requests_do_not_call_upstream(symbol, start, end):
    transport = FixtureTransport("unused")
    instance = AkShareProvider(transport=transport)
    with pytest.raises(ValueError):
        instance.fetch_daily_prices(symbol, start, end)
    assert transport.calls == []


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "301", "bad"])
def test_timeout_environment_rejects_unsafe_values(value):
    with pytest.raises(ConfigurationError):
        load_settings({"MARKET_DATA_TIMEOUT_SECONDS": value})


def test_timeout_configuration():
    assert load_settings({"MARKET_DATA_TIMEOUT_SECONDS": "2.5"}).market_data_timeout_seconds == 2.5
    assert load_settings({}).market_data_timeout_seconds == 30


@pytest.mark.anyio
async def test_provider_error_reuses_http_error_contract(application, client):
    @application.get("/fixture-provider-error")
    async def failure():
        raise ProviderTimeoutError()

    response = await client.get("/fixture-provider-error")
    assert response.status_code == 503
    assert response.json()["code"] == "provider_timeout"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_provider_error_has_safe_summary():
    error = ProviderError(
        "provider_unavailable", "Market data provider unavailable", retryable=True
    )
    assert error.retryable and error.status_code == 503


def test_stock_snapshot_excludes_cdr_without_relaxing_validator():
    table = {"columns": ["code", "name"], "data": [["689009", "模拟CDR"], ["600519", "模拟A股"]]}
    result = provider(json.dumps(table)).fetch_stocks()
    assert [row.symbol for row in result.records] == ["600519.SH"]
    from app.collectors.validator import MarketDataValidationError, normalize_symbol

    with pytest.raises(MarketDataValidationError):
        normalize_symbol("689009.SH")


def test_tencent_explicit_interface_preserves_units_and_shortest_float_values():
    payload = json.dumps(
        {
            "columns": ["date", "open", "high", "low", "close", "volume", "amount"],
            "data": [["2026-09-28", 1399.47, 1400, 1390, 1395, 120000, 1000000000.0000001]],
        }
    )
    transport = FixtureTransport(payload)
    adapter = AkShareProvider(
        Settings(market_data_daily_interface="stock_zh_a_hist_tx"), transport=transport
    )
    batch = adapter.fetch_daily_prices("600519.SH", START, END)
    from app.jobs.collection import SourceProvider

    assert (
        SourceProvider(adapter, "akshare").fetch_daily_prices("600519.SH", START, END).source
        == "akshare_tx"
    )
    assert batch.source == "akshare_tx"
    assert batch.source_interface == "stock_zh_a_hist_tx"
    assert batch.records[0].open == Decimal("1399.47")
    assert batch.records[0].volume_shares == 120000
    assert batch.records[0].amount_cny == Decimal("1000000000.00")
    assert transport.calls[0][1]["symbol"] == "sh600519"
    payload = payload.replace("1000000000.0000001", "12345.678")
    with pytest.raises(ProviderContractError):
        AkShareProvider(
            Settings(market_data_daily_interface="stock_zh_a_hist_tx"),
            transport=FixtureTransport(payload),
        ).fetch_daily_prices("600519.SH", START, END)


def test_tencent_sz000_equity_sdk_lots_are_converted_once():
    payload = json.dumps(
        {
            "columns": ["date", "open", "high", "low", "close", "volume", "amount"],
            "data": [["2026-09-28", 10, 10, 10, 10, 1200, 1200000]],
        }
    )
    adapter = AkShareProvider(
        Settings(market_data_daily_interface="stock_zh_a_hist_tx"),
        transport=FixtureTransport(payload),
    )
    assert adapter.fetch_daily_prices("000001.SZ", START, END).records[0].volume_shares == 120000
    assert adapter.fetch_daily_prices("300750.SZ", START, END).records[0].volume_shares == 1200
