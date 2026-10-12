"""Independent Shanghai after-close scheduler; no imports from the API lifecycle."""

import json
import logging
import signal
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from datetime import time as daytime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.exc import SQLAlchemyError

from app.collectors.akshare import AkShareProvider
from app.collectors.errors import ProviderError
from app.collectors.source_policy import PolicyProvider
from app.collectors.validator import MarketDataValidationError, normalize_symbol
from app.core.config import ConfigurationError, load_settings
from app.core.database import create_configured_database_engine, create_session_factory
from app.core.errors import ApplicationError
from app.core.logging import configure_logging
from app.jobs.cli import SafeParser, UsageError, _emit, _terminate
from app.jobs.collection import CollectionRunner, RetryPolicy
from app.repositories.scheduling import ScheduleRepository
from app.repositories.sync_jobs import SyncJobRepository
from app.services.daily_prices import DailyPriceService
from app.services.stocks import StockService

SHANGHAI = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger("stockinsight.jobs.scheduler")


@dataclass(frozen=True)
class TradingCalendar:
    source: str
    start: date
    end: date
    days: frozenset[date]

    def __post_init__(self):
        if (
            not isinstance(self.source, str)
            or not self.source.strip()
            or len(self.source) > 128
            or type(self.start) is not date
            or type(self.end) is not date
            or self.start > self.end
            or not isinstance(self.days, frozenset)
            or any(
                type(day) is not date or not self.start <= day <= self.end or day.weekday() >= 5
                for day in self.days
            )
        ):
            raise ValueError("Invalid trading calendar")

    @classmethod
    def load(cls, path):
        value = json.loads(Path(path).read_text())
        days = [date.fromisoformat(day) for day in value["trading_dates"]]
        if len(set(days)) != len(days):
            raise ValueError("Duplicate trading calendar day")
        return cls(
            value["source"],
            date.fromisoformat(value["coverage_start"]),
            date.fromisoformat(value["coverage_end"]),
            frozenset(days),
        )

    def due(self, now: datetime, at: daytime):
        if now.utcoffset() is None:
            raise ValueError("Scheduler clock requires timezone")
        local = now.astimezone(SHANGHAI)
        if not self.start <= local.date() <= self.end:
            raise ApplicationError(
                "calendar_coverage_missing", "Trading calendar coverage missing", 422
            )
        return local.date() in self.days and local.time() >= at

    def target_day(self, now: datetime, at: daytime, *, catch_up=False):
        due = self.due(now, at)  # Always enforce timezone and coverage.
        local = now.astimezone(SHANGHAI)
        if due:
            return local.date()
        if catch_up:
            return max((day for day in self.days if day < local.date()), default=None)
        return None


class ReadyProvider:
    """Missing today's close is a visible retryable failure, never a successful stale update."""

    def __init__(self, provider, calendar):
        self.provider, self.calendar = provider, calendar

    @property
    def daily_source(self):
        return getattr(self.provider, "daily_source", "akshare")

    def fetch_daily_prices(self, symbol, start, end):
        batch = self.provider.fetch_daily_prices(symbol, start, end)
        if not any(row.trade_date == end for row in batch.records):
            raise ProviderError(
                "daily_data_not_ready", "Today's daily data is not ready", retryable=True
            )
        if any(row.trade_date not in self.calendar.days for row in batch.records):
            raise ApplicationError(
                "calendar_date_mismatch", "Market rows conflict with calendar", 422
            )
        return batch


class AfterCloseScheduler:
    def __init__(self, repository, runner, calendar, symbols, initial_start, *, at=daytime(17, 30)):
        self.repository, self.runner, self.calendar = repository, runner, calendar
        self.symbols = tuple(normalize_symbol(symbol) for symbol in symbols)
        if (
            not self.symbols
            or len(self.symbols) > 500
            or len(set(self.symbols)) != len(self.symbols)
            or type(initial_start) is not date
            or not calendar.start <= initial_start <= calendar.end
            or not isinstance(at, daytime)
            or at.tzinfo is not None
            or at < daytime(15)
        ):
            raise ValueError("Invalid scheduler configuration")
        self.initial_start, self.at = initial_start, at

    def tick(self, now, *, catch_up=False):
        day = self.calendar.target_day(now, self.at, catch_up=catch_up)
        if day is None:
            return {"status": "not_due", "job_count": 0, "failed_jobs": 0}
        if day < self.initial_start:
            return {"status": "not_due", "job_count": 0, "failed_jobs": 0}
        results, failures, skipped = [], 0, 0
        with self.repository.ownership():
            for symbol in self.symbols:
                scope, resume_id, complete = self.repository.scope(symbol, day, self.initial_start)
                if complete:
                    skipped += 1
                    continue
                try:
                    result = self.runner.run(scope, resume_id=resume_id)
                    results.append(result)
                    failures += result.status != "succeeded"
                except ApplicationError as error:
                    if error.code in {"collection_busy", "active_job_exists"}:
                        raise
                    failures += 1
                    logger.error(
                        "Scheduled symbol failed",
                        extra={"event_data": {"symbol": symbol, "code": error.code}},
                    )
        count = len(results)
        return {
            "status": "partial"
            if failures and (count + skipped > failures)
            else "failed"
            if failures
            else "succeeded",
            "job_count": count,
            "failed_jobs": failures,
            "skipped_jobs": skipped,
        }


def parser():
    result = SafeParser(description="Independent Asia/Shanghai after-close scheduler")
    result.add_argument("--calendar", required=True)
    result.add_argument("--symbol", action="append", required=True)
    result.add_argument("--initial-start", type=date.fromisoformat, required=True)
    result.add_argument("--at", type=daytime.fromisoformat, default=daytime(17, 30))
    result.add_argument("--max-attempts", type=int, default=3)
    result.add_argument("--retry-delay", type=float, default=1)
    result.add_argument("--once", action="store_true")
    result.add_argument(
        "--catch-up", action="store_true", help="Update the last completed trading day at startup"
    )
    return result


def main(argv=None):
    engine = None
    try:
        args = parser().parse_args(argv)
        calendar = TradingCalendar.load(args.calendar)
        retry = RetryPolicy(args.max_attempts, args.retry_delay)
        # Validate all scope/calendar/time parameters before touching the database or provider.
        AfterCloseScheduler(None, None, calendar, args.symbol, args.initial_start, at=args.at)
        calendar.due(datetime.now(UTC), args.at)
        settings = load_settings()
        configure_logging(settings)
        engine = create_configured_database_engine(settings)
        sessions = create_session_factory(engine)
        runner = CollectionRunner(
            SyncJobRepository(engine),
            StockService(sessions),
            DailyPriceService(sessions),
            ReadyProvider(
                PolicyProvider(settings, calendar=calendar)
                if settings.source_policy_directory
                else AkShareProvider(settings),
                calendar,
            ),
            retry=retry,
        )
        scheduler = AfterCloseScheduler(
            ScheduleRepository(engine),
            runner,
            calendar,
            args.symbol,
            args.initial_start,
            at=args.at,
        )
        attempted = None
        while True:
            now = datetime.now(UTC)
            day = calendar.target_day(now, args.at, catch_up=args.catch_up)
            if args.once or day != attempted:
                result = scheduler.tick(now, catch_up=args.catch_up)
                if result["status"] != "not_due":
                    attempted = day  # Bounded retries once per daemon/day; explicit restart or --once retries failures.
                if args.once or result["status"] != "not_due":
                    _emit(
                        "scheduler_result",
                        **result,
                        target_date=day.isoformat() if day else None,
                        calendar_source=calendar.source,
                        coverage_verified=False,
                    )
                if args.once:
                    return 1 if result["failed_jobs"] else 0
            time.sleep(30)
    except (
        UsageError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        ConfigurationError,
        MarketDataValidationError,
    ):
        _emit("scheduler_error", code="invalid_scheduler_configuration")
        return 2
    except ApplicationError as error:
        _emit("scheduler_error", code=error.code)
        return 1
    except SQLAlchemyError:
        _emit("scheduler_error", code="scheduler_storage_error")
        return 1
    except KeyboardInterrupt:
        _emit("scheduler_stopped", code="scheduler_interrupted")
        return 130
    except Exception:
        _emit("scheduler_error", code="scheduler_internal_error")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _terminate)
    raise SystemExit(main())
