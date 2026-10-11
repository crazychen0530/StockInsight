"""Local collection orchestration: bounded retries and idempotent interval replay."""

import logging
import re
import time
from dataclasses import dataclass
from uuid import UUID

from app.collectors.errors import ProviderError
from app.collectors.validator import (
    MarketDataValidationError,
    normalize_symbol,
    validate_date_range,
)
from app.core.errors import ApplicationError
from app.repositories.sync_jobs import JobScope, JobView, SyncJobRepository

logger = logging.getLogger("stockinsight.jobs.collection")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0

    def __post_init__(self):
        if (
            type(self.max_attempts) is not int
            or not 1 <= self.max_attempts <= 5
            or type(self.base_delay) not in (int, float)
            or not 0 <= self.base_delay <= 10
        ):
            raise ApplicationError("invalid_retry_policy", "Invalid retry policy", 422)


def validate_scope(scope: JobScope) -> JobScope:
    if (
        not isinstance(scope.source, str)
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", scope.source)
        or scope.job_type not in {"full", "incremental", "backfill"}
    ):
        raise ApplicationError("invalid_job_scope", "Invalid synchronization scope", 422)
    if scope.symbol is None:
        if scope.job_type != "full" or scope.start_date is not None or scope.end_date is not None:
            raise ApplicationError("invalid_job_scope", "Invalid stock snapshot scope", 422)
        return scope
    symbol = normalize_symbol(scope.symbol)
    start, end = validate_date_range(scope.start_date, scope.end_date)
    return JobScope(scope.source, scope.job_type, symbol, start, end)


class SourceProvider:
    """Reject mismatched provenance before either service can write business data."""

    def __init__(self, provider, source):
        self.provider, self.source = provider, source

    def _check(self, batch):
        if batch.source != self.source:
            raise ApplicationError("provider_source_mismatch", "Provider source mismatch", 422)
        return batch

    def fetch_stocks(self):
        return self._check(self.provider.fetch_stocks())

    def fetch_daily_prices(self, symbol, start_date, end_date):
        return self._check(self.provider.fetch_daily_prices(symbol, start_date, end_date))


class CollectionRunner:
    def __init__(
        self,
        jobs: SyncJobRepository,
        stocks,
        prices,
        provider,
        *,
        source="akshare",
        retry: RetryPolicy | None = None,
        sleep=time.sleep,
    ):
        validate_scope(JobScope(source, "full"))
        self.jobs, self.stocks, self.prices = jobs, stocks, prices
        self.provider, self.source = SourceProvider(provider, source), source
        self.retry, self.sleep = retry if retry is not None else RetryPolicy(), sleep

    def run(self, scope: JobScope, *, resume_id: UUID | None = None) -> JobView:
        scope = validate_scope(scope)
        if scope.source != self.source:
            raise ApplicationError("provider_source_mismatch", "Provider source mismatch", 422)
        with self.jobs.ownership():
            job = self.jobs.get(resume_id) if resume_id else self.jobs.create(scope)
            if job.scope != scope:
                raise ApplicationError("job_scope_mismatch", "Job scope mismatch", 422)
            if job.status == "succeeded":
                return job  # No provider call and no counter changes on completed resume.
            self.jobs.start(job.id)
            logger.info("Collection job started", extra={"event_data": {"job_id": str(job.id)}})
            try:
                result = self._collect(scope, job.id)
            except (ApplicationError, MarketDataValidationError) as error:
                return self.jobs.finish(job.id, total=1 if scope.symbol else 0, code=error.code)
            except Exception:
                self.jobs.finish(
                    job.id, total=1 if scope.symbol else 0, code="collection_internal_error"
                )
                raise  # Defects are recorded safely, never disguised as retryable failures.
            # A crash here leaves running: replay the full atomic scope, never skip an unproven date.
            return self.jobs.finish(
                job.id,
                total=1 if scope.symbol else result.processed_count,
                empty=result.processed_count == 0,
                checkpoint_symbol=(scope.symbol if scope.symbol else result.last_symbol)
                if result.processed_count
                else None,
                checkpoint_date=result.last_trade_date if scope.symbol else None,
            )

    def _collect(self, scope: JobScope, job_id: UUID):
        for attempt in range(self.retry.max_attempts):
            try:
                if scope.symbol:
                    return self.prices.sync(
                        self.provider, scope.symbol, scope.start_date, scope.end_date
                    )
                return self.stocks.sync(self.provider)
            except ProviderError as error:
                if not error.retryable or attempt + 1 == self.retry.max_attempts:
                    raise
                delay = min(30.0, self.retry.base_delay * 2**attempt)
                logger.warning(
                    "Collection retry scheduled",
                    extra={
                        "event_data": {
                            "job_id": str(job_id),
                            "code": error.code,
                            "attempt": attempt + 1,
                            "delay_seconds": delay,
                        }
                    },
                )
                self.sleep(delay)

    def resume(self, job_id: UUID) -> JobView:
        return self.run(self.jobs.get(job_id).scope, resume_id=job_id)
