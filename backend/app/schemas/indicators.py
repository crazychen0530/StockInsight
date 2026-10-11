"""Exact, versioned SMA response with current-day input provenance."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator

from app.analysis.moving_averages import CALCULATION_VERSION
from app.schemas.stocks import DailyPriceListResponse


class IndicatorResponse(BaseModel):
    symbol: str
    trade_date: date
    calculation_version: str
    ma5: Decimal | None
    ma20: Decimal | None
    ma60: Decimal | None
    computed_at: datetime
    source: str
    fetched_at: datetime
    adjustment: Literal["none"]

    @field_validator("computed_at", "fetched_at")
    @classmethod
    def utc_timestamp(cls, value):
        from app.schemas.stocks import DailyPriceResponse

        return DailyPriceResponse.utc_timestamp(value)


class IndicatorListResponse(DailyPriceListResponse):
    items: list[IndicatorResponse]
    calculation_version: str = CALCULATION_VERSION
    source_scope: Literal["current_day_input"] = "current_day_input"
