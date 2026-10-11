"""Simple moving averages of observed trading rows, never calendar-day padding."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.collectors.validator import normalize_symbol

CALCULATION_VERSION = "sma-close-v1"


@dataclass(frozen=True)
class ClosePoint:
    symbol: str
    trade_date: date
    close: Decimal


@dataclass(frozen=True)
class MovingAverage:
    symbol: str
    trade_date: date
    ma5: Decimal | None
    ma20: Decimal | None
    ma60: Decimal | None
    calculation_version: str = CALCULATION_VERSION


def _fits_scale(value: Decimal) -> bool:
    with localcontext() as context:
        context.prec = 40
        return value == value.quantize(Decimal("0.0001"))


def calculate_moving_averages(points: Iterable[ClosePoint]) -> tuple[MovingAverage, ...]:
    groups = defaultdict(list)
    seen = set()
    for point in points:
        if not isinstance(point, ClosePoint) or type(point.trade_date) is not date:
            raise ValueError("Invalid close point")
        symbol = normalize_symbol(point.symbol)
        value = point.close
        if (
            not isinstance(value, Decimal)
            or not value.is_finite()
            or not Decimal(0) <= value <= Decimal("99999999999999.9999")
            or not _fits_scale(value)
        ):
            raise ValueError("Invalid closing price")
        key = symbol, point.trade_date
        if key in seen:
            raise ValueError("Duplicate stock trading date")
        seen.add(key)
        groups[symbol].append(point)
    output = []
    # Explicit context makes results independent of the calling thread's Decimal context.
    with localcontext() as context:
        context.prec, context.rounding = 40, ROUND_HALF_UP
        for symbol, rows in sorted(groups.items()):
            rows.sort(key=lambda row: row.trade_date)
            sums = {5: Decimal(0), 20: Decimal(0), 60: Decimal(0)}
            for index, row in enumerate(rows):
                values = []
                for window in sums:
                    sums[window] += row.close
                    if index >= window:
                        sums[window] -= rows[index - window].close
                    values.append(
                        (sums[window] / window).quantize(Decimal("0.0001"))
                        if index + 1 >= window
                        else None
                    )
                output.append(MovingAverage(symbol, row.trade_date, *values))
    return tuple(output)
