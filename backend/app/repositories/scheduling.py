"""Schedule ownership and durable per-symbol scope selection."""

from contextlib import contextmanager

from sqlalchemy import func, select, text

from app.core.database import create_session_factory
from app.core.errors import ApplicationError
from app.models import DailyPrice, DataSyncJob
from app.repositories.sync_jobs import JobScope

SCHEDULER_LOCK = 7348190502


class ScheduleRepository:
    def __init__(self, engine):
        self.engine = engine
        self.sessions = create_session_factory(engine)

    @contextmanager
    def ownership(self):
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            locked = False
            try:
                locked = bool(
                    conn.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": SCHEDULER_LOCK})
                )
                if not locked:
                    raise ApplicationError("scheduler_busy", "Another scheduler is running", 409)
                yield
            finally:
                try:
                    if locked:
                        conn.execute(
                            text("SELECT pg_advisory_unlock(:key)"), {"key": SCHEDULER_LOCK}
                        )
                finally:
                    conn.invalidate()

    def scope(self, symbol, day, initial_start):
        with self.sessions() as session:
            row = session.scalar(
                select(DataSyncJob)
                .where(
                    DataSyncJob.source == "akshare",
                    DataSyncJob.job_type == "incremental",
                    DataSyncJob.target_symbol == symbol,
                    DataSyncJob.target_end_date == day,
                )
                .order_by(DataSyncJob.started_at.desc(), DataSyncJob.id)
                .limit(1)
            )
            if row is not None:
                scope = JobScope(
                    row.source,
                    row.job_type,
                    row.target_symbol,
                    row.target_start_date,
                    row.target_end_date,
                )
                complete = row.status == "succeeded" and row.checkpoint_date == day
                return scope, None if row.status == "succeeded" else row.id, complete
            latest = session.scalar(
                select(func.max(DailyPrice.trade_date)).where(
                    DailyPrice.symbol == symbol, DailyPrice.trade_date <= day
                )
            )
            return (
                JobScope(
                    "akshare",
                    "incremental",
                    symbol,
                    max(initial_start, latest) if latest else initial_start,
                    day,
                ),
                None,
                False,
            )
