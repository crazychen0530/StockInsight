"""Stock snapshot synchronization and local search without collection HTTP routes."""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.errors import ProviderError
from app.collectors.provider import MarketDataProvider, StockInfo
from app.collectors.validator import MarketDataValidationError, validate_stocks
from app.core.errors import ApplicationError
from app.repositories.stocks import StockRepository

logger = logging.getLogger("stockinsight.services.stocks")


@dataclass(frozen=True)
class StockSyncResult:
    processed_count: int
    changed_count: int
    source: str
    source_interface: str
    fetched_at: datetime


@dataclass(frozen=True)
class StockSearchPage:
    items: tuple[StockInfo, ...]
    total: int
    page: int
    page_size: int


def _storage_error(operation: str) -> ApplicationError:
    logger.error("Stock storage operation failed", extra={"event_data": {"operation": operation}})
    return ApplicationError("stock_storage_error", "Stock storage unavailable", status_code=503)


class StockService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def sync(self, provider: MarketDataProvider) -> StockSyncResult:
        # All network calls and whole-batch validation finish before opening a DB session.
        try:
            batch = validate_stocks(provider.fetch_stocks())
        except ProviderError as error:
            logger.warning("Stock provider failed", extra={"event_data": {"code": error.code}})
            raise
        except MarketDataValidationError as error:
            logger.warning(
                "Stock validation failed",
                extra={
                    "event_data": {
                        "code": error.code,
                        "field": error.field,
                        "row_index": error.row_index,
                    }
                },
            )
            raise
        changed = 0
        if batch.records:
            try:
                with self.session_factory() as session, session.begin():
                    changed = StockRepository(session).upsert(batch.records)
            except SQLAlchemyError:
                raise _storage_error("sync") from None
        result = StockSyncResult(
            len(batch.records), changed, batch.source, batch.source_interface, batch.fetched_at
        )
        logger.info(
            "Stock synchronization finished",
            extra={
                "event_data": {
                    "processed_count": result.processed_count,
                    "changed_count": result.changed_count,
                }
            },
        )
        return result

    def search(self, query: str = "", *, page: int = 1, page_size: int = 20) -> StockSearchPage:
        if (
            not isinstance(query, str)
            or len(query) > 128
            or "\x00" in query
            or type(page) is not int
            or page < 1
            or type(page_size) is not int
            or not 1 <= page_size <= 100
            or (page - 1) * page_size > 2**63 - 1
        ):
            raise ApplicationError("invalid_stock_search", "Invalid stock search parameters", 422)
        try:
            with self.session_factory() as session, session.begin():
                # Keep total and items consistent even when another process synchronizes stocks.
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                items, total = StockRepository(session).search(query.strip(), page, page_size)
        except SQLAlchemyError:
            raise _storage_error("search") from None
        return StockSearchPage(items, total, page, page_size)
