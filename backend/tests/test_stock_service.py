"""Service boundaries with explicitly simulated providers and database failures."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.collectors.errors import ProviderTimeoutError
from app.collectors.provider import MarketDataBatch, StockInfo
from app.collectors.validator import MarketDataValidationError
from app.core.errors import ApplicationError
from app.services.stocks import StockService


class FixtureProvider:
    def __init__(self, records=(), error=None):
        self.records = records
        self.error = error

    def fetch_stocks(self):
        if self.error:
            raise self.error
        return MarketDataBatch(
            self.records, "mock_fixture", "fixture", datetime(2026, 10, 9, tzinfo=UTC)
        )


@pytest.mark.parametrize(
    "query,page,size",
    [
        (None, 1, 20),
        ("x" * 129, 1, 20),
        ("\x00", 1, 20),
        ("", 0, 20),
        ("", True, 20),
        ("", 1.5, 20),
        ("", 1, 0),
        ("", 1, 101),
        ("", 1, True),
        ("", 2**64, 100),
    ],
)
def test_invalid_search_never_opens_database(query, page, size):
    factory = MagicMock()
    with pytest.raises(ApplicationError) as error:
        StockService(factory).search(query, page=page, page_size=size)
    assert error.value.code == "invalid_stock_search"
    factory.assert_not_called()


def test_empty_snapshot_preserves_receipt_without_database():
    factory = MagicMock()
    result = StockService(factory).sync(FixtureProvider())
    assert result.processed_count == result.changed_count == 0
    assert result.source == "mock_fixture" and result.source_interface == "fixture"
    assert result.fetched_at.tzinfo is UTC
    factory.assert_not_called()


@pytest.mark.parametrize(
    "provider,error_type",
    [
        (FixtureProvider(error=ProviderTimeoutError()), ProviderTimeoutError),
        (FixtureProvider((StockInfo("invalid", "测试证券", "SZ"),)), MarketDataValidationError),
    ],
)
def test_provider_or_validation_failure_before_database(provider, error_type):
    factory = MagicMock()
    with pytest.raises(error_type):
        StockService(factory).sync(provider)
    factory.assert_not_called()


@pytest.mark.parametrize("operation", ["sync", "search"])
def test_database_connection_failure_is_safe(operation, capsys):
    factory = MagicMock(side_effect=SQLAlchemyError("password=fixture-storage-secret"))
    service = StockService(factory)
    with pytest.raises(ApplicationError) as error:
        if operation == "sync":
            service.sync(FixtureProvider((StockInfo("000001.SZ", "测试证券", "SZ"),)))
        else:
            service.search("token=fixture-query-secret")
    assert error.value.code == "stock_storage_error"
    output = capsys.readouterr().out
    assert "fixture-storage-secret" not in str(error.value) + output
    assert "fixture-query-secret" not in output


def test_commit_failure_never_reports_success(monkeypatch, capsys):
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    session.begin.return_value.__exit__.side_effect = SQLAlchemyError("fixture-commit-secret")
    repository = MagicMock()
    repository.upsert.return_value = 1
    monkeypatch.setattr("app.services.stocks.StockRepository", MagicMock(return_value=repository))
    with pytest.raises(ApplicationError):
        StockService(factory).sync(FixtureProvider((StockInfo("000001.SZ", "测试证券", "SZ"),)))
    output = capsys.readouterr().out
    assert "Stock synchronization finished" not in output and "fixture-commit-secret" not in output
