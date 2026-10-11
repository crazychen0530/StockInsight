"""Create the initial StockInsight schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the four M1 core tables, constraints, and query indexes."""
    op.create_table(
        "stocks",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("exchange", sa.String(length=8), nullable=False),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.CheckConstraint("exchange IN ('SH', 'SZ')", name="ck_stocks_exchange"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_stocks_name_not_blank"),
        sa.CheckConstraint("length(btrim(status)) > 0", name="ck_stocks_status_not_blank"),
        sa.CheckConstraint("symbol ~ '^[0-9]{6}\\.(SH|SZ)$'", name="ck_stocks_symbol_format"),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_index("ix_stocks_exchange_status", "stocks", ["exchange", "status"])
    op.create_index("ix_stocks_name", "stocks", ["name"])

    op.create_table(
        "daily_prices",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("volume_shares", sa.BigInteger(), nullable=False),
        sa.Column("amount_cny", sa.Numeric(precision=24, scale=2), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("adjustment", sa.String(length=16), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("adjustment = 'none'", name="ck_daily_prices_adjustment_none"),
        sa.CheckConstraint("amount_cny >= 0", name="ck_daily_prices_amount_nonnegative"),
        sa.CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0",
            name="ck_daily_prices_nonnegative_ohlc",
        ),
        sa.CheckConstraint(
            "high >= open AND high >= close AND high >= low AND low <= open AND low <= close",
            name="ck_daily_prices_ohlc_relationship",
        ),
        sa.CheckConstraint("length(btrim(source)) > 0", name="ck_daily_prices_source_not_blank"),
        sa.CheckConstraint("volume_shares >= 0", name="ck_daily_prices_volume_nonnegative"),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stocks.symbol"], name="fk_daily_prices_symbol_stocks"
        ),
        sa.PrimaryKeyConstraint("symbol", "trade_date", name="pk_daily_prices"),
    )
    op.create_index("ix_daily_prices_trade_date", "daily_prices", ["trade_date"])

    op.create_table(
        "technical_indicators",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("calculation_version", sa.String(length=32), nullable=False),
        sa.Column("ma5", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("ma20", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("ma60", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ma20 IS NULL OR ma20 >= 0", name="ck_technical_indicators_ma20_nonnegative"
        ),
        sa.CheckConstraint(
            "ma5 IS NULL OR ma5 >= 0", name="ck_technical_indicators_ma5_nonnegative"
        ),
        sa.CheckConstraint(
            "ma60 IS NULL OR ma60 >= 0", name="ck_technical_indicators_ma60_nonnegative"
        ),
        sa.CheckConstraint(
            "length(btrim(calculation_version)) > 0",
            name="ck_technical_indicators_version_not_blank",
        ),
        sa.ForeignKeyConstraint(
            ["symbol"], ["stocks.symbol"], name="fk_technical_indicators_symbol_stocks"
        ),
        sa.PrimaryKeyConstraint(
            "symbol", "trade_date", "calculation_version", name="pk_technical_indicators"
        ),
    )
    op.create_index(
        "ix_technical_indicators_symbol_trade_date",
        "technical_indicators",
        ["symbol", "trade_date"],
    )

    op.create_table(
        "data_sync_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("target_symbol", sa.String(length=16), nullable=True),
        sa.Column("target_start_date", sa.Date(), nullable=True),
        sa.Column("target_end_date", sa.Date(), nullable=True),
        sa.Column("total_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("success_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("checkpoint_symbol", sa.String(length=16), nullable=True),
        sa.Column("checkpoint_date", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "checkpoint_symbol IS NULL OR checkpoint_symbol ~ '^[0-9]{6}\\.(SH|SZ)$'",
            name="ck_data_sync_jobs_checkpoint_symbol_format",
        ),
        sa.CheckConstraint(
            "total_count >= 0 AND success_count >= 0 AND failure_count >= 0",
            name="ck_data_sync_jobs_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_data_sync_jobs_time_order",
        ),
        sa.CheckConstraint(
            "job_type IN ('full', 'incremental', 'backfill')",
            name="ck_data_sync_jobs_job_type",
        ),
        sa.CheckConstraint(
            "success_count + failure_count <= total_count",
            name="ck_data_sync_jobs_processed_within_total",
        ),
        sa.CheckConstraint("length(btrim(source)) > 0", name="ck_data_sync_jobs_source_not_blank"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'partial', 'failed')",
            name="ck_data_sync_jobs_status",
        ),
        sa.CheckConstraint(
            "(status IN ('pending', 'running') AND finished_at IS NULL) OR "
            "(status IN ('succeeded', 'partial', 'failed') AND finished_at IS NOT NULL)",
            name="ck_data_sync_jobs_status_finished_at",
        ),
        sa.CheckConstraint(
            "(target_start_date IS NULL AND target_end_date IS NULL) OR "
            "(target_start_date IS NOT NULL AND target_end_date IS NOT NULL "
            "AND target_start_date <= target_end_date)",
            name="ck_data_sync_jobs_target_date_range",
        ),
        sa.CheckConstraint(
            "target_symbol IS NULL OR target_symbol ~ '^[0-9]{6}\\.(SH|SZ)$'",
            name="ck_data_sync_jobs_target_symbol_format",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_sync_jobs_source_started_at", "data_sync_jobs", ["source", "started_at"]
    )
    op.create_index(
        "ix_data_sync_jobs_status_started_at", "data_sync_jobs", ["status", "started_at"]
    )
    op.create_index(
        "uq_data_sync_jobs_active_scope",
        "data_sync_jobs",
        ["source", "job_type", "target_symbol", "target_start_date", "target_end_date"],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    """Drop the initial schema in dependency-safe order."""
    op.drop_index("uq_data_sync_jobs_active_scope", table_name="data_sync_jobs")
    op.drop_index("ix_data_sync_jobs_status_started_at", table_name="data_sync_jobs")
    op.drop_index("ix_data_sync_jobs_source_started_at", table_name="data_sync_jobs")
    op.drop_table("data_sync_jobs")
    op.drop_index("ix_technical_indicators_symbol_trade_date", table_name="technical_indicators")
    op.drop_table("technical_indicators")
    op.drop_index("ix_daily_prices_trade_date", table_name="daily_prices")
    op.drop_table("daily_prices")
    op.drop_index("ix_stocks_name", table_name="stocks")
    op.drop_index("ix_stocks_exchange_status", table_name="stocks")
    op.drop_table("stocks")
