"""Read-only local queries; never invoke market-data providers or collection jobs."""

import logging
from collections.abc import Callable
from datetime import date

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.analysis.moving_averages import CALCULATION_VERSION
from app.collectors.validator import (
    MarketDataValidationError,
    normalize_symbol,
    validate_date_range,
)
from app.core.errors import ApplicationError
from app.repositories.daily_prices import DailyPriceRepository
from app.repositories.indicators import IndicatorRepository
from app.repositories.stocks import StockRepository
from app.schemas.indicators import IndicatorListResponse, IndicatorResponse
from app.schemas.stocks import (
    DailyPriceListResponse,
    DailyPriceResponse,
    StockListResponse,
    StockResponse,
)
from app.services.stocks import StockService

logger = logging.getLogger("stockinsight.services.stock_queries")


def _symbol(value: str) -> str:
    try:
        return normalize_symbol(value)
    except MarketDataValidationError:
        raise ApplicationError("invalid_symbol", "Invalid stock symbol", 422) from None


def _missing() -> ApplicationError:
    return ApplicationError("stock_not_found", "Stock not found in local database", 404)


def _unavailable() -> ApplicationError:
    logger.error("Stock query failed", extra={"event_data": {"operation": "query"}})
    return ApplicationError("stock_query_unavailable", "Stock query storage unavailable", 503)


class StockQueryService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def search(self, query: str = "", *, page: int = 1, page_size: int = 20) -> StockListResponse:
        result = StockService(self.session_factory).search(query, page=page, page_size=page_size)
        return StockListResponse(
            items=[StockResponse.model_validate(row) for row in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )

    def detail(self, symbol: str) -> StockResponse:
        canonical = _symbol(symbol)
        try:
            with self.session_factory() as session, session.begin():
                row = StockRepository(session).get(canonical)
                if row is None:
                    raise _missing()
                return StockResponse.model_validate(row)
        except SQLAlchemyError:
            raise _unavailable() from None

    def prices(
        self, symbol: str, start_date: date, end_date: date, *, limit: int = 250
    ) -> DailyPriceListResponse:
        canonical = _symbol(symbol)
        try:
            validate_date_range(start_date, end_date)
        except MarketDataValidationError:
            raise ApplicationError(
                "invalid_date_range", "Invalid daily price date range", 422
            ) from None
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ApplicationError("invalid_price_limit", "Invalid daily price limit", 422)
        try:
            with self.session_factory() as session, session.begin():
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                if not StockRepository(session).exists(canonical):
                    raise _missing()
                rows = DailyPriceRepository(session).query(
                    canonical, start_date, end_date, limit + 1
                )
                return DailyPriceListResponse(
                    symbol=canonical,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    has_more=len(rows) > limit,
                    items=[DailyPriceResponse.model_validate(row) for row in rows[:limit]],
                )
        except SQLAlchemyError:
            raise _unavailable() from None

    def indicators(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        *,
        limit: int = 250,
        calculation_version: str = CALCULATION_VERSION,
    ):
        canonical = _symbol(symbol)
        try:
            validate_date_range(start_date, end_date)
        except MarketDataValidationError:
            raise ApplicationError(
                "invalid_date_range", "Invalid indicator date range", 422
            ) from None
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ApplicationError("invalid_indicator_limit", "Invalid indicator limit", 422)
        if calculation_version != CALCULATION_VERSION:
            raise ApplicationError(
                "unsupported_calculation_version", "Unsupported calculation version", 422
            )
        try:
            with self.session_factory() as session, session.begin():
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                if not StockRepository(session).exists(canonical):
                    raise _missing()
                rows = IndicatorRepository(session).query(
                    canonical, start_date, end_date, calculation_version, limit + 1
                )
                return IndicatorListResponse(
                    symbol=canonical,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    has_more=len(rows) > limit,
                    calculation_version=calculation_version,
                    items=[IndicatorResponse.model_validate(row) for row in rows[:limit]],
                )
        except SQLAlchemyError:
            raise _unavailable() from None
