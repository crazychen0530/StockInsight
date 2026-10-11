"""AKShare-specific field mapping and unit conversion; no business validator."""

import json
import logging
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from app.collectors.akshare_transport import AkShareTransport, SubprocessAkShareTransport
from app.collectors.errors import ProviderContractError, ProviderError
from app.collectors.provider import DailyBar, MarketDataBatch, StockInfo
from app.core.config import Settings, load_settings

logger = logging.getLogger("stockinsight.collectors.akshare")


def _exchange(code: str) -> Literal["SH", "SZ"] | None:
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
        raise ProviderContractError()
    if code.startswith("6"):
        return "SH"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("4", "8", "92")):
        return None  # Beijing is outside the approved SH/SZ scope.
    raise ProviderContractError()


def _number(value: object) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ProviderContractError()
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ProviderContractError() from None
    if not number.is_finite():
        raise ProviderContractError()
    return number


def _rows(payload: str, required: set[str]) -> list[dict]:
    try:
        table = json.loads(payload, parse_float=Decimal)
        columns, data = table["columns"], table["data"]
        if not isinstance(columns, list) or not isinstance(data, list):
            raise ValueError
        if not all(isinstance(column, str) for column in columns):
            raise ValueError
        if len(set(columns)) != len(columns):
            raise ValueError
        # AKShare legitimately returns a completely columnless empty DataFrame.
        if not columns and not data:
            return []
        if not required.issubset(columns):
            raise ValueError
        if any(not isinstance(row, list) or len(row) != len(columns) for row in data):
            raise ValueError
        return [dict(zip(columns, row, strict=True)) for row in data]
    except (ValueError, KeyError, TypeError):
        raise ProviderContractError() from None


class AkShareProvider:
    def __init__(
        self, settings: Settings | None = None, *, transport: AkShareTransport | None = None
    ) -> None:
        self.timeout = (settings or load_settings()).market_data_timeout_seconds
        self.transport = transport if transport is not None else SubprocessAkShareTransport()

    def _fetch(
        self, interface: str, parameters: dict[str, str | float], required: set[str]
    ) -> tuple[list[dict], datetime]:
        try:
            rows = _rows(self.transport.call(interface, parameters, self.timeout), required)
        except ProviderError as error:
            self._log_failure(interface, error)
            raise
        return rows, datetime.now(UTC)

    @staticmethod
    def _log_failure(interface: str, error: ProviderError) -> None:
        logger.warning(
            "Market data provider failed",
            extra={"event_data": {"source": "akshare", "interface": interface, "code": error.code}},
        )

    def fetch_stocks(self) -> MarketDataBatch[StockInfo]:
        interface = "stock_info_a_code_name"
        rows, fetched_at = self._fetch(interface, {}, {"code", "name"})
        records = []
        excluded = 0
        try:
            for row in rows:
                exchange = _exchange(row["code"])
                if exchange is None:
                    excluded += 1
                    continue
                name = row["name"]
                if not isinstance(name, str) or not name.strip():
                    raise ProviderContractError()
                records.append(StockInfo(f"{row['code']}.{exchange}", name.strip(), exchange))
        except ProviderError as error:
            self._log_failure(interface, error)
            raise
        if excluded:
            logger.info(
                "Excluded stocks outside SH/SZ scope",
                extra={"event_data": {"source": "akshare", "excluded_count": excluded}},
            )
        return MarketDataBatch(tuple(records), "akshare", interface, fetched_at)

    def fetch_daily_prices(
        self, symbol: str, start_date: date, end_date: date
    ) -> MarketDataBatch[DailyBar]:
        # Only request safety/adapter requirements here; detailed validation is M2-02.
        if not isinstance(symbol, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", symbol):
            raise ValueError("Expected a canonical SH/SZ symbol")
        code, exchange = symbol.split(".")
        try:
            expected_exchange = _exchange(code)
        except ProviderContractError:
            raise ValueError("Unsupported symbol exchange") from None
        if expected_exchange != exchange:
            raise ValueError("Unsupported symbol exchange")
        if type(start_date) is not date or type(end_date) is not date or start_date > end_date:
            raise ValueError("Expected an inclusive date interval")
        interface = "stock_zh_a_hist"
        rows, fetched_at = self._fetch(
            interface,
            {
                "symbol": code,
                "period": "daily",
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "adjust": "",
                "timeout": self.timeout,
            },
            {"日期", "股票代码", "开盘", "最高", "最低", "收盘", "成交量", "成交额"},
        )
        records = []
        try:
            for row in rows:
                if row["股票代码"] != code:
                    raise ProviderContractError()
                trade_date = date.fromisoformat(row["日期"])
                if not start_date <= trade_date <= end_date:
                    raise ProviderContractError()
                shares = _number(row["成交量"]) * 100
                if shares != shares.to_integral_value():
                    raise ProviderContractError()
                records.append(
                    DailyBar(
                        symbol,
                        trade_date,
                        _number(row["开盘"]),
                        _number(row["最高"]),
                        _number(row["最低"]),
                        _number(row["收盘"]),
                        int(shares),
                        _number(row["成交额"]),
                    )
                )
        except (ValueError, TypeError, ProviderError) as error:
            safe_error = error if isinstance(error, ProviderError) else ProviderContractError()
            self._log_failure(interface, safe_error)
            raise safe_error from None
        return MarketDataBatch(tuple(records), "akshare", interface, fetched_at)
