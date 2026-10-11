"""Persistence model for observable and resumable market-data synchronization jobs."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataSyncJob(Base):
    """One synchronization attempt and its target, counters, and checkpoint."""

    __tablename__ = "data_sync_jobs"
    __table_args__ = (
        CheckConstraint("length(btrim(source)) > 0", name="ck_data_sync_jobs_source_not_blank"),
        CheckConstraint(
            "job_type IN ('full', 'incremental', 'backfill')",
            name="ck_data_sync_jobs_job_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'partial', 'failed')",
            name="ck_data_sync_jobs_status",
        ),
        CheckConstraint(
            "target_symbol IS NULL OR target_symbol ~ '^[0-9]{6}\\.(SH|SZ)$'",
            name="ck_data_sync_jobs_target_symbol_format",
        ),
        CheckConstraint(
            "checkpoint_symbol IS NULL OR checkpoint_symbol ~ '^[0-9]{6}\\.(SH|SZ)$'",
            name="ck_data_sync_jobs_checkpoint_symbol_format",
        ),
        CheckConstraint(
            "(target_start_date IS NULL AND target_end_date IS NULL) OR "
            "(target_start_date IS NOT NULL AND target_end_date IS NOT NULL "
            "AND target_start_date <= target_end_date)",
            name="ck_data_sync_jobs_target_date_range",
        ),
        CheckConstraint(
            "total_count >= 0 AND success_count >= 0 AND failure_count >= 0",
            name="ck_data_sync_jobs_counts_nonnegative",
        ),
        CheckConstraint(
            "success_count + failure_count <= total_count",
            name="ck_data_sync_jobs_processed_within_total",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_data_sync_jobs_time_order",
        ),
        CheckConstraint(
            "(status IN ('pending', 'running') AND finished_at IS NULL) OR "
            "(status IN ('succeeded', 'partial', 'failed') AND finished_at IS NOT NULL)",
            name="ck_data_sync_jobs_status_finished_at",
        ),
        Index("ix_data_sync_jobs_status_started_at", "status", "started_at"),
        Index("ix_data_sync_jobs_source_started_at", "source", "started_at"),
        Index(
            "uq_data_sync_jobs_active_scope",
            "source",
            "job_type",
            "target_symbol",
            "target_start_date",
            "target_end_date",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    checkpoint_symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    checkpoint_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
