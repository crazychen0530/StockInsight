"""Provider-independent, immutable data contracts. Business validation is M2-02."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class StockInfo:
    symbol: str
    name: str
    exchange: Literal["SH", "SZ"]
    list_date: date | None = None
    status: str = "unknown"


@dataclass(frozen=True)
class DailyBar:
    symbol: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_shares: int
    amount_cny: Decimal


@dataclass(frozen=True)
class MarketDataBatch[T]:
    """Metadata survives even an empty response; fetched_at is aware UTC."""

    records: tuple[T, ...]
    source: str
    source_interface: str
    fetched_at: datetime
    adjustment: Literal["none"] = "none"
    price_unit: Literal["CNY"] = "CNY"
    volume_unit: Literal["share"] = "share"
    amount_unit: Literal["CNY"] = "CNY"


@runtime_checkable
class MarketDataProvider(Protocol):
    def fetch_stocks(self) -> MarketDataBatch[StockInfo]:
        """Fetch the provider's SH/SZ A-share identity snapshot."""
        ...

    def fetch_daily_prices(
        self, symbol: str, start_date: date, end_date: date
    ) -> MarketDataBatch[DailyBar]:
        """Fetch unadjusted daily prices for an inclusive date interval."""
        ...
