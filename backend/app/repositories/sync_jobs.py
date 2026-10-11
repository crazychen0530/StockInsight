"""Short transactions for job state and a dedicated collection ownership connection."""

import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import Engine, select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import create_session_factory
from app.core.errors import ApplicationError
from app.models import DataSyncJob


@dataclass(frozen=True)
class JobScope:
    source: str
    job_type: str
    symbol: str | None = None
    start_date: date | None = None
    end_date: date | None = None


@dataclass(frozen=True)
class JobView:
    id: UUID
    scope: JobScope
    status: str
    total_count: int
    success_count: int
    failure_count: int
    checkpoint_symbol: str | None
    checkpoint_date: date | None
    error_code: str | None


def _view(row: DataSyncJob) -> JobView:
    return JobView(
        row.id,
        JobScope(
            row.source, row.job_type, row.target_symbol, row.target_start_date, row.target_end_date
        ),
        row.status,
        row.total_count,
        row.success_count,
        row.failure_count,
        row.checkpoint_symbol,
        row.checkpoint_date,
        row.error_message
        if row.error_message is None or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", row.error_message)
        else "stored_error_redacted",
    )


class SyncJobRepository:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.sessions = create_session_factory(engine)

    @contextmanager
    def ownership(self):
        # Coarse, database-wide CLI mutex also serializes overlapping scopes and job types.
        # No business transaction is held during provider calls or retry delays.
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            try:
                if not connection.scalar(text("SELECT pg_try_advisory_lock(7348190501)")):
                    raise ApplicationError(
                        "collection_busy", "Another collector owns the database", 409
                    )
                yield
            finally:
                # Physically close this dedicated session, never return a held lock to the pool.
                connection.invalidate()

    def create(self, scope: JobScope) -> JobView:
        try:
            with self.sessions() as session, session.begin():
                row = DataSyncJob(
                    source=scope.source,
                    job_type=scope.job_type,
                    target_symbol=scope.symbol,
                    target_start_date=scope.start_date,
                    target_end_date=scope.end_date,
                    started_at=datetime.now(UTC),
                    status="pending",
                    total_count=1 if scope.symbol else 0,
                    success_count=0,
                    failure_count=0,
                )
                session.add(row)
                session.flush()
                result = _view(row)
            return result
        except IntegrityError as error:
            if (
                getattr(getattr(error.orig, "diag", None), "constraint_name", None)
                != "uq_data_sync_jobs_active_scope"
            ):
                raise
            raise ApplicationError(
                "active_job_exists", "Resume the existing active job", 409
            ) from None

    def get(self, job_id: UUID) -> JobView:
        with self.sessions() as session:
            row = session.get(DataSyncJob, job_id)
            if row is None:
                raise ApplicationError("job_not_found", "Synchronization job not found", 404)
            return _view(row)

    def list_recent(self, limit: int = 20) -> tuple[JobView, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ApplicationError("invalid_job_limit", "Invalid job list limit", 422)
        with self.sessions() as session:
            return tuple(
                _view(row)
                for row in session.scalars(
                    select(DataSyncJob)
                    .order_by(DataSyncJob.started_at.desc(), DataSyncJob.id)
                    .limit(limit)
                )
            )

    def start(self, job_id: UUID) -> None:
        with self.sessions() as session, session.begin():
            row = session.get(DataSyncJob, job_id, with_for_update=True)
            row.status, row.finished_at, row.error_message = "running", None, None
            row.started_at = datetime.now(UTC)
            row.success_count = row.failure_count = 0

    def finish(
        self,
        job_id: UUID,
        *,
        total: int,
        code: str | None = None,
        empty: bool = False,
        checkpoint_symbol: str | None = None,
        checkpoint_date: date | None = None,
    ) -> JobView:
        with self.sessions() as session, session.begin():
            row = session.get(DataSyncJob, job_id, with_for_update=True)
            row.total_count = total
            row.success_count = 0 if code else total
            row.failure_count = total if code else 0
            row.status = "failed" if code else "succeeded"
            row.finished_at = max(datetime.now(UTC), row.started_at)
            row.error_message = code or ("empty_response_coverage_unverified" if empty else None)
            row.checkpoint_symbol, row.checkpoint_date = checkpoint_symbol, checkpoint_date
            result = _view(row)
        return result
