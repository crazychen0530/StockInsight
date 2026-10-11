"""Private one-call SDK isolation, not a collection CLI or scheduler."""

import json
import logging
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import date


def main() -> int:
    request = json.load(sys.stdin)
    if request["interface"] not in {"stock_info_a_code_name", "stock_zh_a_hist"}:
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
            if "日期" in frame.columns:
                frame["日期"] = frame["日期"].map(
                    lambda value: value.isoformat() if isinstance(value, date) else value
                )
            payload = frame.to_json(orient="split", date_format="iso", double_precision=15)
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
