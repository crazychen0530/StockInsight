"""Deterministic tests using simulated values, never actual market quotes."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal, Inexact, localcontext
from pathlib import Path

import pytest

from app.collectors.akshare import AkShareProvider
from app.collectors.provider import DailyBar, MarketDataBatch, StockInfo
from app.collectors.validator import (
    MarketDataValidationError,
    normalize_symbol,
    validate_daily_prices,
    validate_date_range,
    validate_stocks,
)
from app.core.config import Settings

START, END = date(2026, 9, 28), date(2026, 9, 29)
FETCHED = datetime(2026, 9, 29, 10, tzinfo=UTC)
D = Decimal


def bar(**changes):
    return replace(
        DailyBar("000001.SZ", START, D("10"), D("12"), D("9"), D("11"), 1200, D("12345.67")),
        **changes,
    )


def batch(records=(), **changes):
    return replace(MarketDataBatch(tuple(records), "mock_fixture", "fixture", FETCHED), **changes)


def check(rows=(), **metadata):
    return validate_daily_prices(batch(rows, **metadata), "000001.SZ", START, END)


def assert_error(code, field, function, *args, **kwargs):
    with pytest.raises(MarketDataValidationError) as failure:
        function(*args, **kwargs)
    assert (failure.value.code, failure.value.field) == (code, field)
    return failure.value


@pytest.mark.parametrize(
    "symbol",
    [
        "600000.SH",
        "601000.SH",
        "603000.SH",
        "605000.SH",
        "688001.SH",
        "000001.SZ",
        "001200.SZ",
        "001999.SZ",
        "002001.SZ",
        "003001.SZ",
        "300001.SZ",
        "301001.SZ",
        "309799.SZ",
    ],
)
def test_supported_a_share_code_segments(symbol):
    assert normalize_symbol(symbol) == symbol


def test_symbol_normalization_never_guesses_market_or_zeros():
    assert normalize_symbol(" 000001.sz ") == "000001.SZ"
    for value in ("000001", 1, "1.SZ", "sh600000", "０００００１.SZ", None, "000 001.SZ"):
        assert_error("invalid_symbol", "symbol", normalize_symbol, value)


@pytest.mark.parametrize(
    "symbol",
    [
        "600000.SZ",
        "000001.SH",
        "920001.BJ",
        "700001.SH",
        "900001.SH",
        "200001.SZ",
        "510300.SH",
        "399001.SZ",
        "001199.SZ",
        "309800.SZ",
        "689001.SH",
        "004001.SZ",
    ],
)
def test_unknown_exchange_non_a_share_and_unsupported_segments(symbol):
    with pytest.raises(MarketDataValidationError):
        normalize_symbol(symbol)


def test_daily_sort_is_deterministic_without_mutating_input_or_units():
    first, second = bar(), bar(trade_date=END)
    original = batch((second, replace(first, symbol=" 000001.sz ")))
    result = validate_daily_prices(original, "000001.sz", START, END)
    assert result.records == (first, second)
    assert original.records[0].trade_date == END
    assert original.records[1].symbol == " 000001.sz "
    assert result.records[0].volume_shares == 1200  # Already shares; never multiply again.
    assert (result.source, result.source_interface, result.fetched_at, result.adjustment) == (
        original.source,
        original.source_interface,
        FETCHED,
        "none",
    )
    assert validate_daily_prices(result, "000001.SZ", START, END) == result


@pytest.mark.parametrize(
    "validator", [validate_stocks, lambda b: validate_daily_prices(b, "000001.SZ", START, END)]
)
def test_empty_is_explicit_valid_batch_with_metadata(validator):
    original = batch()
    assert validator(original) == original
    assert validator(original).records == ()


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("source", "", "invalid_text"),
        ("source", "x" * 33, "text_too_long"),
        ("source", " mock_fixture", "invalid_metadata"),
        ("source", "x\x00y", "invalid_text"),
        ("source_interface", "", "invalid_text"),
        ("source_interface", "x" * 129, "text_too_long"),
        ("adjustment", "qfq", "unsupported_metadata"),
        ("volume_unit", "lot", "unsupported_metadata"),
        ("price_unit", "USD", "unsupported_metadata"),
        ("amount_unit", "10k_CNY", "unsupported_metadata"),
        ("fetched_at", datetime(2026, 9, 29), "invalid_timestamp"),
        ("fetched_at", "2026-09-29", "invalid_timestamp"),
    ],
)
@pytest.mark.parametrize("kind", ["stocks", "daily"])
def test_invalid_metadata_rejected_even_for_empty_batches(kind, field, value, code):
    function = validate_stocks if kind == "stocks" else check
    args = (batch(**{field: value}),) if kind == "stocks" else ()
    kwargs = {} if kind == "stocks" else {field: value}
    assert_error(code, field, function, *args, **kwargs)


def test_aware_timestamps_normalize_to_utc_without_changing_instant():
    local_time = FETCHED.astimezone(timezone(timedelta(hours=8)))
    result = check((bar(),), fetched_at=local_time)
    assert result.fetched_at == local_time and result.fetched_at.tzinfo is UTC
    assert result.fetched_at == FETCHED


@pytest.mark.parametrize(
    "start,end,code",
    [
        (END, START, "invalid_date_range"),
        ("2026-09-28", END, "invalid_date"),
        (datetime(2026, 9, 28), END, "invalid_date"),
        (START, None, "invalid_date"),
    ],
)
def test_invalid_date_range(start, end, code):
    with pytest.raises(MarketDataValidationError) as failure:
        validate_date_range(start, end)
    assert failure.value.code == code


def test_single_day_interval_is_inclusive():
    assert validate_date_range(START, START) == (START, START)
    assert validate_daily_prices(batch((bar(),)), "000001.SZ", START, START).records == (bar(),)


@pytest.mark.parametrize(
    "value,code",
    [
        ("2026-09-28", "invalid_date"),
        (datetime(2026, 9, 28), "invalid_date"),
        (None, "invalid_date"),
        (date(2026, 9, 30), "date_out_of_range"),
    ],
)
def test_invalid_row_date(value, code):
    assert_error(code, "trade_date", check, (bar(trade_date=value),))


def test_duplicate_day_is_rejected_with_row_index_without_dropping_rows():
    original = batch((bar(), bar()))
    error = assert_error(
        "duplicate_trade_date",
        "trade_date",
        validate_daily_prices,
        original,
        "000001.SZ",
        START,
        END,
    )
    assert error.row_index == 1 and len(original.records) == 2


def test_symbol_correlation():
    assert_error("symbol_mismatch", "symbol", check, (bar(symbol="600519.SH"),))


def test_weekend_and_explicit_holiday_calendar():
    saturday = date(2026, 9, 26)
    assert_error(
        "non_trading_date",
        "trade_date",
        validate_daily_prices,
        batch((bar(trade_date=saturday),)),
        "000001.SZ",
        saturday,
        END,
    )
    assert_error(
        "non_trading_date",
        "trade_date",
        validate_daily_prices,
        batch((bar(),)),
        "000001.SZ",
        START,
        END,
        trading_dates=frozenset({END}),
    )
    assert validate_daily_prices(
        batch((bar(),)), "000001.SZ", START, END, trading_dates={START}
    ).records == (bar(),)
    assert_error(
        "non_trading_date",
        "trade_date",
        validate_daily_prices,
        batch((bar(),)),
        "000001.SZ",
        START,
        END,
        trading_dates=set(),
    )


@pytest.mark.parametrize("calendar", [[START], {"2026-09-28"}, {datetime(2026, 9, 28)}])
def test_calendar_must_be_an_explicit_date_set(calendar):
    assert_error(
        "invalid_calendar",
        "trading_dates",
        validate_daily_prices,
        batch(),
        "000001.SZ",
        START,
        END,
        trading_dates=calendar,
    )


def test_future_dates_use_snapshot_business_day_not_wall_clock():
    # At UTC 16:01, Shanghai is already the next day.
    stamp = datetime(2026, 9, 28, 16, 1, tzinfo=UTC)
    assert check((bar(trade_date=END),), fetched_at=stamp).records[0].trade_date == END
    assert_error(
        "future_trade_date",
        "trade_date",
        check,
        (bar(trade_date=END),),
        fetched_at=datetime(2026, 9, 28, 10, tzinfo=UTC),
    )


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "amount_cny"])
@pytest.mark.parametrize("value", [None, 10.1, "10.1", True, D("NaN"), D("sNaN"), D("Infinity")])
def test_missing_wrong_type_and_nonfinite_decimals(field, value):
    assert_error("invalid_decimal", field, check, (bar(**{field: value}),))


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "amount_cny"])
def test_negative_price_and_amount_rejected(field):
    assert_error("negative_value", field, check, (bar(**{field: D("-0.01")}),))


@pytest.mark.parametrize(
    "changes",
    [
        {"open": D("13")},
        {"close": D("8")},
        {"low": D("11")},
        {"high": D("8")},
    ],
)
def test_ohlc_relationships(changes):
    assert_error("invalid_ohlc", "ohlc", check, (bar(**changes),))


def test_zero_ohlcv_and_equal_prices_remain_valid_without_inventing_quotes():
    zero = bar(
        open=D("0"), high=D("0"), low=D("0"), close=D("0"), volume_shares=0, amount_cny=D("0")
    )
    assert check((zero,)).records == (zero,)


@pytest.mark.parametrize(
    "value,code",
    [
        (True, "invalid_integer"),
        (1.0, "invalid_integer"),
        (D("1"), "invalid_integer"),
        (None, "invalid_integer"),
        (-1, "integer_out_of_range"),
        (2**63, "integer_out_of_range"),
    ],
)
def test_volume_integer_and_bigint_boundaries(value, code):
    assert_error(code, "volume_shares", check, (bar(volume_shares=value),))


def test_decimal_and_bigint_maximum_exactly_fit_schema():
    maximum = D("99999999999999.9999")
    row = bar(
        open=maximum,
        high=maximum,
        low=maximum,
        close=maximum,
        volume_shares=2**63 - 1,
        amount_cny=D("9999999999999999999999.99"),
    )
    assert check((row,)).records == (row,)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("close", D("10.12345"), "excess_precision"),
        ("amount_cny", D("100.001"), "excess_precision"),
        ("high", D("100000000000000"), "numeric_overflow"),
        ("amount_cny", D("10000000000000000000000"), "numeric_overflow"),
        ("close", D("1e-1000000"), "excess_precision"),
        ("high", D("1e1000000"), "numeric_overflow"),
    ],
)
def test_precision_overflow_and_extreme_exponents_do_not_round(field, value, code):
    assert_error(code, field, check, (bar(**{field: value}),))


def test_trailing_zeros_and_decimal_context_do_not_change_validation():
    row = bar(open=D("10.100000"), amount_cny=D("12345.67000"))
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        assert check((row,)).records == (row,)
        assert_error("excess_precision", "close", check, (bar(close=D("10.12345")),))


def test_stocks_normalize_sort_and_preserve_unknowns():
    first = StockInfo(" 000001.sz ", " 测试证券 ", "SZ")
    second = StockInfo("600519.SH", "测试证券SH", "SH", date(2000, 1, 1), "listed")
    original = batch((second, first))
    result = validate_stocks(original)
    assert result.records == (replace(first, symbol="000001.SZ", name="测试证券"), second)
    assert result.records[0].list_date is None and result.records[0].status == "unknown"
    assert original.records == (second, first)
    assert validate_stocks(result) == result


def test_exact_decimal_canonicalization_bounds_redundant_exponents_without_rounding():
    zero = D("0E+1000000")
    row = bar(low=zero, amount_cny=D("12345.670000"))
    result = check((row,)).records[0]
    assert result.low.as_tuple() == D("0").as_tuple()
    assert result.amount_cny.as_tuple() == D("12345.67").as_tuple()
    assert row.low.as_tuple() == zero.as_tuple()
    assert row.amount_cny.as_tuple() == D("12345.670000").as_tuple()


@pytest.mark.parametrize(
    "changes,code,field",
    [
        ({"name": " "}, "invalid_text", "name"),
        ({"name": "x" * 129}, "text_too_long", "name"),
        ({"status": None}, "invalid_text", "status"),
        ({"status": "x" * 25}, "text_too_long", "status"),
        ({"exchange": "SH"}, "exchange_mismatch", "exchange"),
        ({"list_date": "2020-01-01"}, "invalid_date", "list_date"),
        ({"list_date": date(2026, 9, 30)}, "future_list_date", "list_date"),
    ],
)
def test_stock_failures(changes, code, field):
    row = replace(StockInfo("000001.SZ", "测试证券", "SZ"), **changes)
    assert_error(code, field, validate_stocks, batch((row,)))


def test_duplicate_stock_after_normalization_is_not_silently_overwritten():
    row = StockInfo("000001.SZ", "测试证券", "SZ")
    error = assert_error(
        "duplicate_symbol",
        "symbol",
        validate_stocks,
        batch((row, replace(row, symbol="000001.sz"))),
    )
    assert error.row_index == 1


def test_error_diagnostics_do_not_include_input_values():
    error = assert_error(
        "invalid_symbol", "symbol", check, (bar(symbol="password=fixture-validator-secret"),)
    )
    assert error.row_index == 0
    assert "fixture-validator-secret" not in str(error) + repr(error)


@pytest.mark.parametrize(
    "function", [validate_stocks, lambda b: validate_daily_prices(b, "000001.SZ", START, END)]
)
def test_invalid_record_containers_and_batch_types(function):
    assert_error("invalid_batch", "records", function, None)
    assert_error("invalid_batch", "records", function, replace(batch(), records=[]))
    assert_error("invalid_record", "records", function, batch(({},)))


def test_adapter_fixture_to_validator_preserves_the_single_unit_conversion():
    class Transport:
        def call(self, interface, parameters, timeout):
            path = Path(__file__).parent / "fixtures" / "akshare"
            payload = json.loads(
                (
                    path
                    / ("stocks.json" if interface == "stock_info_a_code_name" else "daily.json")
                ).read_text()
            )
            return json.dumps(payload)

    provider = AkShareProvider(Settings(app_env="test"), transport=Transport())
    stocks = validate_stocks(provider.fetch_stocks())
    prices = validate_daily_prices(
        provider.fetch_daily_prices("000001.SZ", START, END), "000001.SZ", START, END
    )
    assert len(stocks.records) == 4  # Beijing was excluded by the adapter.
    assert prices.records[0].volume_shares == 1200
    assert prices.records[0].amount_cny == D("12345.67")
    assert prices.source == "akshare" and prices.adjustment == "none"
