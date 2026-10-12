"""Finite, operator-reviewed exchange notices; never infer a halt from absent prices."""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class TradingHalt:
    symbol: str
    start: date
    confirmed_through: date
    source_url: str
    published_at: date
    verified_at: date

    def __post_init__(self):
        source = urlsplit(self.source_url)
        host = source.hostname or ""
        official = any(
            host == domain or host.endswith("." + domain)
            for domain in ("szse.cn", "sse.com.cn", "cninfo.com.cn")
        )
        if (
            not isinstance(self.symbol, str)
            or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", self.symbol)
            or self.start > self.confirmed_through
            or self.published_at > self.verified_at
            or source.scheme != "https"
            or source.username is not None
            or not official
        ):
            raise ValueError("Invalid reviewed trading halt")


@dataclass(frozen=True)
class TradingHalts:
    records: tuple[TradingHalt, ...]

    @classmethod
    def load(cls, path):
        value = json.loads(Path(path).read_text())
        if value.get("version") != 1 or not isinstance(value.get("records"), list):
            raise ValueError("Invalid trading halt registry")
        if len(value["records"]) > 500:
            raise ValueError("Too many trading halt records")
        records = tuple(
            TradingHalt(
                row["symbol"],
                date.fromisoformat(row["start"]),
                date.fromisoformat(row["confirmed_through"]),
                row["source_url"],
                date.fromisoformat(row["published_at"]),
                date.fromisoformat(row["verified_at"]),
            )
            for row in value["records"]
        )
        for index, record in enumerate(records):
            if any(
                other.symbol == record.symbol
                and other.start <= record.confirmed_through
                and record.start <= other.confirmed_through
                for other in records[:index]
            ):
                raise ValueError("Overlapping trading halt records")
        return cls(records)

    def expected_day(self, symbol, target, trading_days):
        def halted(day):
            return any(
                row.symbol == symbol and row.start <= day <= row.confirmed_through
                for row in self.records
            )

        if not halted(target):
            return target
        return max((day for day in trading_days if day <= target and not halted(day)), default=None)
