"""Simulated providers and storage faults; no real market data or network."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.collectors.errors import ProviderTimeoutError
from app.collectors.provider import DailyBar, MarketDataBatch
from app.collectors.validator import MarketDataValidationError
from app.core.errors import ApplicationError
from app.services.daily_prices import DailyPriceFailure, DailyPriceService

START, END = date(2026, 9, 28), date(2026, 9, 29)
FETCHED = datetime(2026, 10, 9, tzinfo=UTC)


def bar(symbol="000001.SZ", day=START, **changes):
    return replace(
        DailyBar(
            symbol,
            day,
            Decimal("10"),
            Decimal("12"),
            Decimal("9"),
            Decimal("11"),
            1200,
            Decimal("12345.67"),
        ),
        **changes,
    )


class FixtureDailyProvider:
    def __init__(self, data=None, fetched_at=FETCHED):
        self.data = data or {}
        self.fetched_at = fetched_at
        self.calls = []

    def fetch_daily_prices(self, symbol, start_date, end_date):
        self.calls.append((symbol, start_date, end_date))
        value = self.data.get(symbol, ())
        if isinstance(value, Exception):
            raise value
        return MarketDataBatch(tuple(value), "mock_fixture", "fixture_daily", self.fetched_at)


@pytest.fixture
def mocked_storage(monkeypatch):
    monkeypatch.setattr("app.services.daily_prices.IndicatorService.recalculate", MagicMock())
    factory = MagicMock()
    repository = MagicMock()
    repository.upsert.return_value = 1
    stock = MagicMock()
    stock.exists.return_value = True
    monkeypatch.setattr(
        "app.services.daily_prices.DailyPriceRepository", MagicMock(return_value=repository)
    )
    monkeypatch.setattr("app.services.daily_prices.StockRepository", MagicMock(return_value=stock))
    return DailyPriceService(factory), factory, repository, stock


def test_single_collection_validates_before_session_and_preserves_units(mocked_storage):
    service, factory, repository, stock = mocked_storage

    class Provider(FixtureDailyProvider):
        def fetch_daily_prices(self, *args):
            factory.assert_not_called()
            return super().fetch_daily_prices(*args)

    provider = Provider({"000001.SZ": (bar(day=END), bar())})
    result = service.sync(provider, " 000001.sz ", START, END, trading_dates={START, END})
    assert provider.calls == [("000001.SZ", START, END)]
    written = repository.upsert.call_args.args[0]
    assert written.records == (bar(), bar(day=END))
    assert written.records[0].volume_shares == 1200
    assert (result.processed_count, result.changed_count) == (2, 1)
    assert (result.source, result.source_interface, result.fetched_at) == (
        "mock_fixture",
        "fixture_daily",
        FETCHED,
    )
    stock.exists.assert_called_once_with("000001.SZ")


def test_empty_response_preserves_metadata_without_database():
    factory = MagicMock()
    result = DailyPriceService(factory).sync(FixtureDailyProvider(), "000001.SZ", START, END)
    assert result.processed_count == result.changed_count == 0
    assert result.fetched_at == FETCHED and result.source == "mock_fixture"
    factory.assert_not_called()


@pytest.mark.parametrize(
    "value,error_type",
    [
        (ProviderTimeoutError(), ProviderTimeoutError),
        ((bar(close=Decimal("99")),), MarketDataValidationError),
        ((bar(day=date(2026, 9, 30)),), MarketDataValidationError),
        ((bar(), bar()), MarketDataValidationError),
    ],
)
def test_provider_and_validation_failure_never_opens_database(value, error_type):
    factory = MagicMock()
    with pytest.raises(error_type):
        DailyPriceService(factory).sync(
            FixtureDailyProvider({"000001.SZ": value}), "000001.SZ", START, END
        )
    factory.assert_not_called()


@pytest.mark.parametrize(
    "symbols,start,end,calendar",
    [
        ("000001.SZ", START, END, None),
        (("000001.SZ", "bad"), START, END, None),
        (("000001.SZ", "000001.sz"), START, END, None),
        (("000001.SZ",), END, START, None),
        (("000001.SZ",), START, END, [START]),
        ((), START, END, {"bad"}),
    ],
)
def test_invalid_batch_request_fails_before_any_collection(symbols, start, end, calendar):
    provider, factory = FixtureDailyProvider(), MagicMock()
    with pytest.raises(MarketDataValidationError):
        DailyPriceService(factory).sync_many(provider, symbols, start, end, trading_dates=calendar)
    assert provider.calls == []
    factory.assert_not_called()


def test_missing_stock_requires_identity_sync(mocked_storage):
    service, _, repository, stock = mocked_storage
    stock.exists.return_value = False
    with pytest.raises(ApplicationError) as failure:
        service.sync(FixtureDailyProvider({"000001.SZ": (bar(),)}), "000001.SZ", START, END)
    assert failure.value.code == "daily_stock_missing"
    repository.upsert.assert_not_called()


@pytest.mark.parametrize("stage", ["connect", "write", "commit"])
def test_storage_failure_is_safe_and_never_reports_success(stage, mocked_storage, capsys):
    service, factory, repository, _ = mocked_storage
    error = SQLAlchemyError("password=fixture-daily-storage-secret")
    if stage == "connect":
        factory.side_effect = error
    elif stage == "write":
        repository.upsert.side_effect = error
    else:
        factory.return_value.__enter__.return_value.begin.return_value.__exit__.side_effect = error
    with pytest.raises(ApplicationError) as failure:
        service.sync(FixtureDailyProvider({"000001.SZ": (bar(),)}), "000001.SZ", START, END)
    assert failure.value.code == "daily_price_storage_error"
    output = capsys.readouterr().out
    assert "fixture-daily-storage-secret" not in str(failure.value) + output
    assert "Daily price synchronization finished" not in output


def test_partial_failure_keeps_order_and_continues_to_next_security(mocked_storage):
    service, _, _, _ = mocked_storage
    symbols = ("000001.SZ", "000002.SZ", "600519.SH", "688001.SH")
    provider = FixtureDailyProvider(
        {
            symbols[0]: (bar(symbols[0]),),
            symbols[1]: ProviderTimeoutError(),
            symbols[2]: (bar(symbols[2], close=Decimal("99")),),
        }
    )
    result = service.sync_many(provider, symbols, START, END)
    assert (result.status, result.success_count, result.failure_count, result.empty_count) == (
        "partial",
        2,
        2,
        1,
    )
    assert [row.symbol for row in result.results] == list(symbols)
    assert result.results[1] == DailyPriceFailure(symbols[1], "provider_timeout")
    assert result.results[2] == DailyPriceFailure(symbols[2], "invalid_ohlc", "ohlc", 0)
    assert len(provider.calls) == 4


def test_all_failed_empty_request_and_empty_responses():
    service = DailyPriceService(MagicMock())
    failed = service.sync_many(
        FixtureDailyProvider({"000001.SZ": ProviderTimeoutError()}), ("000001.SZ",), START, END
    )
    assert failed.status == "failed" and failed.failure_count == 1
    assert service.sync_many(FixtureDailyProvider(), (), START, END).status == "empty"
    empty = service.sync_many(FixtureDailyProvider(), ("000001.SZ",), START, END)
    assert empty.status == "succeeded" and empty.empty_count == 1  # Execution only, no data proof.


def test_unexpected_programming_failure_is_not_disguised_as_a_retryable_result():
    provider = FixtureDailyProvider({"000001.SZ": RuntimeError("fixture-programming-error")})
    with pytest.raises(RuntimeError):
        DailyPriceService(MagicMock()).sync_many(provider, ("000001.SZ",), START, END)
