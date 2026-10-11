"""Explicit interval collection with one atomic transaction per security."""

import logging
from collections.abc import Sequence, Set
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.errors import ProviderError
from app.collectors.provider import MarketDataProvider
from app.collectors.validator import (
    MarketDataValidationError,
    normalize_symbol,
    validate_daily_prices,
    validate_date_range,
    validate_trading_dates,
)
from app.core.errors import ApplicationError
from app.repositories.daily_prices import DailyPriceRepository
from app.repositories.stocks import StockRepository

logger = logging.getLogger("stockinsight.services.daily_prices")


@dataclass(frozen=True)
class DailyPriceSyncResult:
    symbol: str
    start_date: date
    end_date: date
    processed_count: int
    changed_count: int
    source: str
    source_interface: str
    fetched_at: datetime


@dataclass(frozen=True)
class DailyPriceFailure:
    symbol: str
    code: str
    field: str | None = None
    row_index: int | None = None


@dataclass(frozen=True)
class DailyPriceBatchResult:
    results: tuple[DailyPriceSyncResult | DailyPriceFailure, ...]

    @property
    def success_count(self) -> int:
        return sum(isinstance(row, DailyPriceSyncResult) for row in self.results)

    @property
    def failure_count(self) -> int:
        return len(self.results) - self.success_count

    @property
    def empty_count(self) -> int:
        return sum(
            isinstance(row, DailyPriceSyncResult) and row.processed_count == 0
            for row in self.results
        )

    @property
    def status(self) -> Literal["empty", "succeeded", "partial", "failed"]:
        if not self.results:
            return "empty"
        if not self.failure_count:
            return "succeeded"
        return "partial" if self.success_count else "failed"


def _log_failure(symbol: str, code: str, **context) -> None:
    logger.warning(
        "Daily price synchronization failed",
        extra={"event_data": {"symbol": symbol, "code": code, **context}},
    )


class DailyPriceService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def sync(
        self,
        provider: MarketDataProvider,
        symbol: str,
        start_date: date,
        end_date: date,
        *,
        trading_dates: Set[date] | None = None,
    ) -> DailyPriceSyncResult:
        symbol = normalize_symbol(symbol)
        start_date, end_date = validate_date_range(start_date, end_date)
        calendar = validate_trading_dates(trading_dates)
        # Fetch and validate the whole security before any database session is opened.
        try:
            batch = validate_daily_prices(
                provider.fetch_daily_prices(symbol, start_date, end_date),
                symbol,
                start_date,
                end_date,
                trading_dates=calendar,
            )
        except ProviderError as error:
            _log_failure(symbol, error.code)
            raise
        except MarketDataValidationError as error:
            _log_failure(symbol, error.code, field=error.field, row_index=error.row_index)
            raise
        changed = 0
        if batch.records:
            try:
                with self.session_factory() as session, session.begin():
                    if not StockRepository(session).exists(symbol):
                        _log_failure(symbol, "daily_stock_missing")
                        raise ApplicationError(
                            "daily_stock_missing",
                            "Synchronize stock identity before daily prices",
                            404,
                        )
                    changed = DailyPriceRepository(session).upsert(batch)
            except SQLAlchemyError:
                _log_failure(symbol, "daily_price_storage_error")
                raise ApplicationError(
                    "daily_price_storage_error", "Daily price storage unavailable", 503
                ) from None
        result = DailyPriceSyncResult(
            symbol,
            start_date,
            end_date,
            len(batch.records),
            changed,
            batch.source,
            batch.source_interface,
            batch.fetched_at,
        )
        # Commit has completed before a successful result or log can escape.
        logger.info(
            "Daily price synchronization finished",
            extra={
                "event_data": {
                    "symbol": symbol,
                    "processed_count": result.processed_count,
                    "changed_count": result.changed_count,
                }
            },
        )
        return result

    def sync_many(
        self,
        provider: MarketDataProvider,
        symbols: Sequence[str],
        start_date: date,
        end_date: date,
        *,
        trading_dates: Set[date] | None = None,
    ) -> DailyPriceBatchResult:
        # Fail invalid requests before the first provider call or committed security.
        if isinstance(symbols, (str, bytes)) or not isinstance(symbols, Sequence):
            raise MarketDataValidationError("invalid_symbols", "symbols")
        canonical = tuple(normalize_symbol(symbol) for symbol in symbols)
        if len(set(canonical)) != len(canonical):
            raise MarketDataValidationError("duplicate_symbol", "symbols")
        start_date, end_date = validate_date_range(start_date, end_date)
        calendar = validate_trading_dates(trading_dates)
        results = []
        for symbol in canonical:
            try:
                results.append(
                    self.sync(provider, symbol, start_date, end_date, trading_dates=calendar)
                )
            except (MarketDataValidationError, ApplicationError) as error:
                results.append(
                    DailyPriceFailure(
                        symbol,
                        error.code,
                        error.field if isinstance(error, MarketDataValidationError) else None,
                        error.row_index if isinstance(error, MarketDataValidationError) else None,
                    )
                )
        result = DailyPriceBatchResult(tuple(results))
        logger.info(
            "Daily price batch finished",
            extra={
                "event_data": {
                    "success_count": result.success_count,
                    "failure_count": result.failure_count,
                    "empty_count": result.empty_count,
                    "status": result.status,
                }
            },
        )
        return result
