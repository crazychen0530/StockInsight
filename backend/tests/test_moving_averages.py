"""Fixed simulated closes, including boundaries and prefix invariance."""

from datetime import date, timedelta
from decimal import Decimal, localcontext

import pytest

from app.analysis.moving_averages import ClosePoint, calculate_moving_averages


def points(count=65, symbol="000001.SZ"):
    return [
        ClosePoint(symbol, date(2026, 1, 1) + timedelta(days=i * 2), Decimal(i + 1))
        for i in range(count)
    ]


def test_windows_sorting_grouping_and_no_mutation():
    data = points()[::-1] + points(4, "600519.SH")
    original = list(data)
    result = calculate_moving_averages(data)
    assert data == original
    assert result[3].ma5 is None and result[4].ma5 == Decimal("3.0000")
    assert result[18].ma20 is None and result[19].ma20 == Decimal("10.5000")
    assert result[58].ma60 is None and result[59].ma60 == Decimal("30.5000")
    assert result[64].ma60 == Decimal("35.5000")
    assert result[-1].ma5 is None
    assert calculate_moving_averages([]) == ()


def test_every_prefix_is_unchanged_by_future_data():
    full = calculate_moving_averages(points())
    for size in range(66):
        assert calculate_moving_averages(points(size)) == full[:size]


@pytest.mark.parametrize(
    "value",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-1"),
        Decimal("0.00001"),
        Decimal("100000000000000"),
        1.2,
        None,
    ],
)
def test_invalid_close(value):
    with pytest.raises(ValueError):
        calculate_moving_averages([ClosePoint("000001.SZ", date(2026, 1, 1), value)])


def test_duplicates_and_invalid_date():
    with pytest.raises(ValueError):
        calculate_moving_averages(points(1) * 2)
    with pytest.raises(ValueError):
        calculate_moving_averages([ClosePoint("000001.SZ", "2026-01-01", Decimal(1))])


def test_rounding_and_decimal_context_independence():
    data = [ClosePoint(p.symbol, p.trade_date, Decimal("99999999999999.9999")) for p in points()]
    expected = calculate_moving_averages(data)
    with localcontext() as context:
        context.prec = 6
        assert calculate_moving_averages(data) == expected
    assert expected[-1].ma60 == Decimal("99999999999999.9999")
