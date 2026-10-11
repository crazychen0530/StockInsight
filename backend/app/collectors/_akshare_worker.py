"""Private one-call SDK isolation, not a collection CLI or scheduler."""

import json
import logging
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import date


def main() -> int:
    request = json.load(sys.stdin)
    if request["interface"] not in {
        "stock_info_a_code_name",
        "stock_zh_a_hist",
        "stock_zh_a_hist_tx",
    }:
        return 11
    # Third-party logs/progress/raw exception messages never cross into app output.
    logging.disable(logging.CRITICAL)
    with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
        try:
            import akshare
            from requests.exceptions import Timeout
        except ImportError:
            return 13
        try:
            frame = getattr(akshare, request["interface"])(**request["parameters"])
            for column in ("日期", "date"):
                if column not in frame.columns:
                    continue
                frame[column] = frame[column].map(
                    lambda value: value.isoformat() if isinstance(value, date) else value
                )
            # pandas' JSON encoder exposes binary float tails (e.g. 1399.47
            # becomes 1399.470000000000027). Python's shortest round-trip
            # representation preserves the SDK value without inventing precision.
            payload = json.dumps(frame.to_dict(orient="split"), default=str, allow_nan=False)
        except Timeout:
            return 10
        except (KeyError, ValueError, TypeError, AttributeError):
            return 11
        except Exception:
            return 12
    sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
