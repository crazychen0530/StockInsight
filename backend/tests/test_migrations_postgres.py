"""PostgreSQL acceptance checks for the initial Alembic migration."""

import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.models import DailyPrice, DataSyncJob, Stock, TechnicalIndicator

EXPECTED_TABLES = {
    "alembic_version",
    "stocks",
    "daily_prices",
    "technical_indicators",
    "data_sync_jobs",
}
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL migration tests")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith(
        "_migration_test"
    ):
        pytest.fail("Use postgresql+psycopg and a disposable database ending in _migration_test")
    return value


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPOSITORY_ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(REPOSITORY_ROOT / "backend" / "alembic"))
    return config


@pytest.mark.postgres
def test_initial_migration_upgrade_constraints_and_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _test_database_url()
    config = _alembic_config(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    engine = sa.create_engine(database_url)
    # Never reset a database supplied by the caller. Acceptance starts on an empty database.
    assert sa.inspect(engine).get_table_names() == [], "Migration test requires an empty database"
    command.upgrade(config, "head")
    command.check(config)

    inspector = sa.inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    assert {column["name"] for column in inspector.get_columns("daily_prices")} >= {
        "volume_shares",
        "amount_cny",
        "fetched_at",
    }
    assert {index["name"] for index in inspector.get_indexes("data_sync_jobs")} >= {
        "ix_data_sync_jobs_status_started_at",
        "uq_data_sync_jobs_active_scope",
    }

    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO stocks (symbol, name, exchange, list_date, status) "
                "VALUES ('600519.SH', '贵州茅台', 'SH', '2001-08-27', 'listed')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO daily_prices "
                "(symbol, trade_date, open, high, low, close, volume_shares, amount_cny, "
                "source, adjustment, fetched_at) VALUES "
                "('600519.SH', '2026-10-09', 1500, 1510, 1490, 1505, 1000, 1505000, "
                "'fixture', 'none', CURRENT_TIMESTAMP)"
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO daily_prices "
                    "(symbol, trade_date, open, high, low, close, volume_shares, amount_cny, "
                    "source, adjustment, fetched_at) VALUES "
                    "('600519.SH', '2026-10-10', 1500, 1490, 1480, 1505, 1000, 1505000, "
                    "'fixture', 'none', CURRENT_TIMESTAMP)"
                )
            )

    active_job_sql = sa.text(
        "INSERT INTO data_sync_jobs "
        "(source, job_type, target_start_date, target_end_date, started_at, status) VALUES "
        "('fixture', 'incremental', '2026-10-09', '2026-10-09', CURRENT_TIMESTAMP, 'running')"
    )
    with engine.begin() as connection:
        connection.execute(active_job_sql)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(active_job_sql)

    now = datetime.now(UTC)
    indicator = {
        "symbol": "600519.SH",
        "trade_date": date(2026, 10, 9),
        "calculation_version": "fixture-v1",
        "computed_at": now,
    }
    with engine.begin() as connection:
        connection.execute(sa.insert(TechnicalIndicator), indicator)
        row = connection.execute(sa.select(TechnicalIndicator.__table__)).mappings().one()
        assert row["ma5"] is None
        price = connection.execute(sa.select(DailyPrice.__table__)).mappings().one()
        assert price["close"] == Decimal("1505.0000")
        assert price["fetched_at"].utcoffset() == timedelta(0)

    cases = [
        (
            Stock,
            {"symbol": "600519.SH", "name": "fixture", "exchange": "SH", "status": "listed"},
            "stocks_pkey",
        ),
        (
            Stock,
            {"symbol": "bad", "name": "fixture", "exchange": "SH", "status": "listed"},
            "ck_stocks_symbol_format",
        ),
        (
            TechnicalIndicator,
            {**indicator, "symbol": "000001.SZ"},
            "fk_technical_indicators_symbol_stocks",
        ),
        (
            TechnicalIndicator,
            {**indicator, "calculation_version": "negative", "ma5": -1},
            "ck_technical_indicators_ma5_nonnegative",
        ),
        (TechnicalIndicator, indicator, "pk_technical_indicators"),
    ]
    price_values = dict(price)
    for changes, constraint in [
        ({}, "pk_daily_prices"),
        ({"symbol": "000001.SZ"}, "fk_daily_prices_symbol_stocks"),
        (
            {"trade_date": date(2026, 10, 10), "volume_shares": -1},
            "ck_daily_prices_volume_nonnegative",
        ),
        (
            {"trade_date": date(2026, 10, 10), "amount_cny": -1},
            "ck_daily_prices_amount_nonnegative",
        ),
        (
            {"trade_date": date(2026, 10, 10), "adjustment": "qfq"},
            "ck_daily_prices_adjustment_none",
        ),
    ]:
        cases.append((DailyPrice, {**price_values, **changes}, constraint))
    job = {"source": "fixture-negative", "job_type": "full", "started_at": now, "status": "running"}
    for changes, constraint in [
        ({"status": "unknown"}, "ck_data_sync_jobs_status"),
        ({"job_type": "unknown"}, "ck_data_sync_jobs_job_type"),
        ({"total_count": -1}, "ck_data_sync_jobs_counts_nonnegative"),
        ({"total_count": 1, "success_count": 2}, "ck_data_sync_jobs_processed_within_total"),
        ({"target_start_date": date(2026, 10, 10)}, "ck_data_sync_jobs_target_date_range"),
        (
            {"target_start_date": date(2026, 10, 10), "target_end_date": date(2026, 10, 9)},
            "ck_data_sync_jobs_target_date_range",
        ),
        ({"status": "succeeded"}, "ck_data_sync_jobs_status_finished_at"),
        (
            {"status": "failed", "finished_at": now - timedelta(seconds=1)},
            "ck_data_sync_jobs_time_order",
        ),
    ]:
        cases.append((DataSyncJob, {**job, **changes}, constraint))
    for model, values, expected_constraint in cases:
        with pytest.raises(IntegrityError) as error:
            with engine.begin() as connection:
                connection.execute(sa.insert(model), values)
        assert error.value.orig.diag.constraint_name == expected_constraint

    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE data_sync_jobs SET status = 'succeeded', finished_at = CURRENT_TIMESTAMP"
            )
        )
        connection.execute(active_job_sql)  # Terminal attempts release the same-scope guard.

    command.downgrade(config, "base")
    assert sa.inspect(engine).get_table_names() == ["alembic_version"]
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    engine.dispose()
