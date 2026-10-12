"""Resolve the explicitly selected secret file then exec without logging credentials."""

import os
import sys
from pathlib import Path


def main():
    if not sys.argv[1:]:
        raise ValueError("Missing process command")
    path = os.environ.get("PGPASSWORD_FILE")
    if path:
        value = Path(path).read_text().strip()
        if not value or "\n" in value:
            raise ValueError("Invalid database password file")
        os.environ["PGPASSWORD"] = value
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError):
        raise SystemExit(
            "Process initialization failed; check mounted secrets and command"
        ) from None
