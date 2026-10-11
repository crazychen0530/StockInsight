"""Stock read routes; all storage and query logic lives below the router."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.analysis.moving_averages import CALCULATION_VERSION
from app.api.dependencies import get_stock_query_service
from app.schemas.indicators import IndicatorListResponse
from app.schemas.stocks import DailyPriceListResponse, StockListResponse, StockResponse
from app.services.stock_queries import StockQueryService

router = APIRouter(prefix="/stocks", tags=["stocks"])
Service = Annotated[StockQueryService, Depends(get_stock_query_service)]


@router.get("", response_model=StockListResponse)
def list_stocks(
    service: Service,
    query: Annotated[str, Query(max_length=128)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StockListResponse:
    return service.search(query, page=page, page_size=page_size)


@router.get("/{symbol}", response_model=StockResponse)
def stock_detail(symbol: str, service: Service) -> StockResponse:
    return service.detail(symbol)


@router.get("/{symbol}/prices", response_model=DailyPriceListResponse)
def daily_prices(
    symbol: str,
    service: Service,
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
    limit: Annotated[int, Query(ge=1, le=1000)] = 250,
) -> DailyPriceListResponse:
    return service.prices(symbol, start_date, end_date, limit=limit)


@router.get("/{symbol}/indicators", response_model=IndicatorListResponse)
def indicators(
    symbol: str,
    service: Service,
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
    limit: Annotated[int, Query(ge=1, le=1000)] = 250,
    calculation_version: Annotated[str, Query(max_length=32)] = CALCULATION_VERSION,
):
    return service.indicators(
        symbol, start_date, end_date, limit=limit, calculation_version=calculation_version
    )
