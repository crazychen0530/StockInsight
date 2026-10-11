"""Deterministic validation of internal DTOs; no network, ORM, logging, or Web imports."""

import re
from collections.abc import Set
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.collectors.provider import DailyBar, MarketDataBatch, StockInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
BIGINT_MAX = 2**63 - 1


class MarketDataValidationError(ValueError):
    """Only fixed rule/field identifiers and a row index; never raw input values."""

    def __init__(self, code: str, field: str, row_index: int | None = None) -> None:
        self.code = code
        self.field = field
        self.row_index = row_index
        super().__init__(f"Market data validation failed: {code} ({field}, row={row_index})")


def normalize_symbol(value: str, *, row_index: int | None = None) -> str:
    """Normalize case/outer whitespace, but never infer an exchange or lost zeros."""
    if not isinstance(value, str):
        raise MarketDataValidationError("invalid_symbol", "symbol", row_index)
    symbol = value.strip().upper()
    if not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", symbol):
        raise MarketDataValidationError("invalid_symbol", "symbol", row_index)
    code, exchange = symbol.split(".")
    # Supported A-share segments, not a claim that a particular security exists.
    sh = code.startswith(("600", "601", "603", "605", "688"))
    sz = (
        code.startswith(("000", "002", "003"))
        or "001200" <= code <= "001999"
        or "300000" <= code <= "309799"
    )
    if not ((exchange == "SH" and sh) or (exchange == "SZ" and sz)):
        raise MarketDataValidationError("unsupported_symbol", "symbol", row_index)
    return symbol


def _date(value: object, field: str, index: int | None = None) -> date:
    # datetime is a subclass of date, but silently truncating a timestamp is unsafe.
    if type(value) is not date:
        raise MarketDataValidationError("invalid_date", field, index)
    return value


def validate_date_range(start_date: date, end_date: date) -> tuple[date, date]:
    start, end = _date(start_date, "start_date"), _date(end_date, "end_date")
    if start > end:
        raise MarketDataValidationError("invalid_date_range", "date_range")
    return start, end


def _text(value: object, field: str, maximum: int, index: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise MarketDataValidationError("invalid_text", field, index)
    result = value.strip()
    if len(result) > maximum:
        raise MarketDataValidationError("text_too_long", field, index)
    return result


def _metadata[T](batch: MarketDataBatch[T]) -> MarketDataBatch[T]:
    if not isinstance(batch, MarketDataBatch) or not isinstance(batch.records, tuple):
        raise MarketDataValidationError("invalid_batch", "records")
    # Source fields are provenance: validate without silently rewriting their values.
    for field, maximum in (("source", 32), ("source_interface", 128)):
        value = getattr(batch, field)
        if _text(value, field, maximum) != value:
            raise MarketDataValidationError("invalid_metadata", field)
    for field, expected in (
        ("adjustment", "none"),
        ("price_unit", "CNY"),
        ("volume_unit", "share"),
        ("amount_unit", "CNY"),
    ):
        if getattr(batch, field) != expected:
            raise MarketDataValidationError("unsupported_metadata", field)
    fetched_at = batch.fetched_at
    if not isinstance(fetched_at, datetime) or fetched_at.utcoffset() is None:
        raise MarketDataValidationError("invalid_timestamp", "fetched_at")
    try:
        utc_time = fetched_at.astimezone(UTC)
        utc_time.astimezone(SHANGHAI)  # Ensure the business date is representable too.
    except (OverflowError, ValueError):
        raise MarketDataValidationError("invalid_timestamp", "fetched_at") from None
    return replace(batch, fetched_at=utc_time)


def _decimal(value: object, field: str, precision: int, scale: int, index: int) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise MarketDataValidationError("invalid_decimal", field, index)
    if value < 0:
        raise MarketDataValidationError("negative_value", field, index)
    if value.is_zero():
        return Decimal(0)
    # Inspect exact digits instead of quantize/normalize, which depend on ambient context.
    _, digits, exponent = value.as_tuple()
    trailing_zeros = 0
    for digit in reversed(digits):
        if digit != 0:
            break
        trailing_zeros += 1
    if value.adjusted() >= precision - scale:
        raise MarketDataValidationError("numeric_overflow", field, index)
    if max(0, -exponent - trailing_zeros) > scale:
        raise MarketDataValidationError("excess_precision", field, index)
    # Canonical exact representation also avoids sending huge redundant exponents to SQL.
    return Decimal((0, digits[: len(digits) - trailing_zeros], exponent + trailing_zeros))


def validate_stocks(batch: MarketDataBatch[StockInfo]) -> MarketDataBatch[StockInfo]:
    normalized = _metadata(batch)
    business_date = normalized.fetched_at.astimezone(SHANGHAI).date()
    records = []
    seen = set()
    for index, row in enumerate(normalized.records):
        if not isinstance(row, StockInfo):
            raise MarketDataValidationError("invalid_record", "records", index)
        symbol = normalize_symbol(row.symbol, row_index=index)
        if row.exchange != symbol[-2:]:
            raise MarketDataValidationError("exchange_mismatch", "exchange", index)
        if symbol in seen:
            raise MarketDataValidationError("duplicate_symbol", "symbol", index)
        seen.add(symbol)
        name = _text(row.name, "name", 128, index)
        status = _text(row.status, "status", 24, index)
        if row.list_date is not None:
            if _date(row.list_date, "list_date", index) > business_date:
                raise MarketDataValidationError("future_list_date", "list_date", index)
        records.append(replace(row, symbol=symbol, name=name, status=status))
    return replace(normalized, records=tuple(sorted(records, key=lambda row: row.symbol)))


def validate_daily_prices(
    batch: MarketDataBatch[DailyBar],
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    trading_dates: Set[date] | None = None,
) -> MarketDataBatch[DailyBar]:
    expected_symbol = normalize_symbol(symbol)
    start, end = validate_date_range(start_date, end_date)
    normalized = _metadata(batch)
    if trading_dates is not None:
        if not isinstance(trading_dates, Set) or any(
            type(day) is not date for day in trading_dates
        ):
            raise MarketDataValidationError("invalid_calendar", "trading_dates")
    business_date = normalized.fetched_at.astimezone(SHANGHAI).date()
    records = []
    seen = set()
    for index, row in enumerate(normalized.records):
        if not isinstance(row, DailyBar):
            raise MarketDataValidationError("invalid_record", "records", index)
        canonical = normalize_symbol(row.symbol, row_index=index)
        if canonical != expected_symbol:
            raise MarketDataValidationError("symbol_mismatch", "symbol", index)
        day = _date(row.trade_date, "trade_date", index)
        if not start <= day <= end:
            raise MarketDataValidationError("date_out_of_range", "trade_date", index)
        if day > business_date:
            raise MarketDataValidationError("future_trade_date", "trade_date", index)
        if day.weekday() >= 5 or (trading_dates is not None and day not in trading_dates):
            raise MarketDataValidationError("non_trading_date", "trade_date", index)
        if day in seen:
            raise MarketDataValidationError("duplicate_trade_date", "trade_date", index)
        seen.add(day)
        prices = {
            field: _decimal(getattr(row, field), field, 18, 4, index)
            for field in ("open", "high", "low", "close")
        }
        if not (row.low <= row.open <= row.high and row.low <= row.close <= row.high):
            raise MarketDataValidationError("invalid_ohlc", "ohlc", index)
        if type(row.volume_shares) is not int:
            raise MarketDataValidationError("invalid_integer", "volume_shares", index)
        if not 0 <= row.volume_shares <= BIGINT_MAX:
            raise MarketDataValidationError("integer_out_of_range", "volume_shares", index)
        amount = _decimal(row.amount_cny, "amount_cny", 24, 2, index)
        records.append(replace(row, symbol=canonical, **prices, amount_cny=amount))
    return replace(normalized, records=tuple(sorted(records, key=lambda row: row.trade_date)))
