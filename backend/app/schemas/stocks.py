"""Public read contracts; Decimal JSON strings preserve stored precision."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    exchange: Literal["SH", "SZ"]
    list_date: date | None
    status: str
    source: str | None = None
    fetched_at: datetime | None = None


class StockListResponse(BaseModel):
    items: list[StockResponse]
    total: int
    page: int
    page_size: int


class DailyPriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_shares: int
    amount_cny: Decimal
    source: str
    fetched_at: datetime
    adjustment: Literal["none"]

    @field_validator("fetched_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Stored price timestamp must have a timezone")
        return value.astimezone(UTC)


class DailyPriceListResponse(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    items: list[DailyPriceResponse]
    limit: int
    has_more: bool
    adjustment: Literal["none"] = "none"
    price_unit: Literal["CNY"] = "CNY"
    volume_unit: Literal["share"] = "share"
    amount_unit: Literal["CNY"] = "CNY"
