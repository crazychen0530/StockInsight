"""Create fresh local test databases and run the full backend suite; retain every database.

Usage: .venv/bin/python scripts/test_postgres.py
Requires local Compose .env credentials and a reachable loopback PostgreSQL server.
Never connects to a developer business database, truncates an existing DB, or prints credentials.
"""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql


def main():
    root = Path(__file__).resolve().parents[1]
    values = {}
    for line in (root / ".env").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip("\"'")
    environment = dict(
        os.environ,
        APP_ENV="test",
        PGHOST="127.0.0.1",
        PGPORT=values.get("POSTGRES_PORT", "5432"),
        PGUSER=values.get("POSTGRES_USER", "stockinsight"),
        PGPASSWORD=values["POSTGRES_PASSWORD"],
    )
    suffixes = {
        "STOCK_TEST_DATABASE_URL": "stocks_test",
        "DAILY_PRICE_TEST_DATABASE_URL": "prices_test",
        "JOB_TEST_DATABASE_URL": "jobs_test",
        "TEST_DATABASE_URL": "migration_test",
        "QUERY_API_TEST_DATABASE_URL": "query_api_test",
        "INDICATOR_TEST_DATABASE_URL": "indicators_test",
    }
    with psycopg.connect(
        host=environment["PGHOST"],
        port=environment["PGPORT"],
        user=environment["PGUSER"],
        password=environment["PGPASSWORD"],
        dbname="postgres",
        autocommit=True,
    ) as connection:
        for key, suffix in suffixes.items():
            name = f"stockinsight_{uuid4().hex[:12]}_{suffix}"
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
            )
            environment[key] = "postgresql+psycopg:///" + name
            print(f"Created isolated database: {name}", flush=True)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "backend", "-q"],
        cwd=root,
        env=environment,
        check=False,
    ).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, psycopg.Error):
        print(
            "Local PostgreSQL test setup failed; verify .env and loopback connectivity",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
