"""Read-only Eastmoney network and configured SDK probes; never open a database."""

import argparse
import json
import time
from datetime import date

import requests
from app.collectors.akshare import AkShareProvider
from app.collectors.errors import ProviderError
from app.collectors.validator import (
    normalize_symbol,
    validate_daily_prices,
    validate_date_range,
)
from app.core.config import Settings


def exception_types(error: BaseException) -> list[str]:
    """Keep useful nested network error types without raw URLs or credentials."""
    pending, seen, names = [error], set(), []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        name = type(current).__name__
        if name not in names:
            names.append(name)
        nested = [
            current.__cause__,
            current.__context__,
            getattr(current, "reason", None),
        ]
        nested.extend(current.args)
        pending.extend(value for value in nested if isinstance(value, BaseException))
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="600519.SH", type=normalize_symbol)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    validate_date_range(args.start, args.end)
    code, exchange = args.symbol.split(".")
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",  # SDK public fixed parameter
        "secid": f"{1 if exchange == 'SH' else 0}.{code}",
        "klt": "101",
        "fqt": "0",
        "beg": args.start.strftime("%Y%m%d"),
        "end": args.end.strftime("%Y%m%d"),
    }
    for mode in ("direct", "environment"):
        result = {"probe": "eastmoney_http", "mode": mode}
        started = time.monotonic()
        try:
            with requests.Session() as session:
                session.trust_env = mode == "environment"
                response = session.get(
                    "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                    params=params,
                    timeout=(6, 12),
                )
                result["http_status"] = response.status_code
                response.raise_for_status()
                payload = response.json()
                result["rows"] = len((payload.get("data") or {}).get("klines", []))
        except (
            requests.RequestException,
            ValueError,
            TypeError,
            AttributeError,
        ) as error:
            result["exception_types"] = exception_types(error)
        result["seconds"] = round(time.monotonic() - started, 2)
        print(json.dumps(result), flush=True)
    successes = 0
    for interface in ("stock_zh_a_hist", "stock_zh_a_hist_tx"):
        result = {"probe": "provider_validation", "interface": interface}
        try:
            provider = AkShareProvider(
                Settings(
                    market_data_daily_interface=interface,
                    market_data_timeout_seconds=45,
                )
            )
            batch = provider.fetch_daily_prices(args.symbol, args.start, args.end)
            checked = validate_daily_prices(batch, args.symbol, args.start, args.end)
            result.update(rows=len(checked.records), source=checked.source)
            if checked.records:
                result.update(
                    first=str(checked.records[0].trade_date),
                    last=str(checked.records[-1].trade_date),
                )
                successes += 1
        except (ProviderError, ValueError) as error:
            result.update(
                exception_types=exception_types(error),
                code=getattr(error, "code", None),
            )
        print(json.dumps(result), flush=True)
    return 0 if successes == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
