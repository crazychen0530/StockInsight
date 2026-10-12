"""Translate a validated operator-owned universe into the existing scheduler CLI."""

import json
import os
import re
from datetime import date
from pathlib import Path


def arguments(path="/config/scheduler.json"):
    value = json.loads(Path(path).read_text())
    symbols = value["symbols"]
    if (
        not isinstance(symbols, list)
        or not 1 <= len(symbols) <= 100
        or len(set(symbols)) != len(symbols)
        or any(
            not isinstance(s, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", s)
            for s in symbols
        )
    ):
        raise ValueError("Invalid production stock universe")
    date.fromisoformat(value["initial_start"])
    halts = value.get("stock_halts_file")
    if halts is not None and halts != "/config/calendars/stock_halts.json":
        raise ValueError("Invalid reviewed stock halt file")
    return [
        "python",
        "-m",
        "app.jobs.scheduler",
        "--calendar",
        "/config/calendars/sse_szse_2026.json",
        "--initial-start",
        value["initial_start"],
        "--catch-up",
        *(["--stock-halts", halts] if halts else []),
        *[part for symbol in symbols for part in ("--symbol", symbol)],
    ]


if __name__ == "__main__":
    try:
        args = arguments()
        os.execvp(args[0], args)
    except (OSError, KeyError, TypeError, ValueError):
        raise SystemExit("Invalid production scheduler configuration") from None
