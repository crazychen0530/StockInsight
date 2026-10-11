"""Fast metadata-level checks for the initial persistence model contract."""

from sqlalchemy import CheckConstraint

from app.core.database import Base
from app.models import DailyPrice, DataSyncJob, Stock, TechnicalIndicator


def test_initial_metadata_contains_only_planned_tables() -> None:
    assert set(Base.metadata.tables) == {
        "stocks",
        "daily_prices",
        "technical_indicators",
        "data_sync_jobs",
    }


def test_model_primary_keys_match_data_dictionary() -> None:
    assert [column.name for column in Stock.__table__.primary_key.columns] == ["symbol"]
    assert [column.name for column in DailyPrice.__table__.primary_key.columns] == [
        "symbol",
        "trade_date",
    ]
    assert [column.name for column in TechnicalIndicator.__table__.primary_key.columns] == [
        "symbol",
        "trade_date",
        "calculation_version",
    ]
    assert [column.name for column in DataSyncJob.__table__.primary_key.columns] == ["id"]


def test_sync_job_model_has_target_counters_checkpoint_and_active_scope_index() -> None:
    columns = set(DataSyncJob.__table__.columns.keys())
    assert {
        "target_symbol",
        "target_start_date",
        "target_end_date",
        "total_count",
        "success_count",
        "failure_count",
        "checkpoint_symbol",
        "checkpoint_date",
    } <= columns

    index = next(
        item
        for item in DataSyncJob.__table__.indexes
        if item.name == "uq_data_sync_jobs_active_scope"
    )
    assert index.unique is True
    assert index.dialect_options["postgresql"]["where"] is not None
    assert index.dialect_options["postgresql"]["nulls_not_distinct"] is True


def test_models_declare_database_check_constraints() -> None:
    constraint_names = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_stocks_symbol_format",
        "ck_daily_prices_ohlc_relationship",
        "ck_daily_prices_adjustment_none",
        "ck_technical_indicators_ma60_nonnegative",
        "ck_data_sync_jobs_target_date_range",
        "ck_data_sync_jobs_processed_within_total",
        "ck_data_sync_jobs_status_finished_at",
    } <= constraint_names
