"""Controlled local CLI. No implicit migrations, scheduler, or fixture data mode."""

import argparse
import json
import signal
from dataclasses import asdict
from datetime import date
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.analysis.moving_averages import CALCULATION_VERSION
from app.collectors.akshare import AkShareProvider
from app.collectors.validator import MarketDataValidationError, normalize_symbol
from app.core.config import ConfigurationError, load_settings
from app.core.database import create_configured_database_engine, create_session_factory
from app.core.errors import ApplicationError
from app.core.logging import Redactor, configure_logging
from app.jobs.collection import CollectionRunner, RetryPolicy, validate_scope
from app.repositories.sync_jobs import JobScope, SyncJobRepository
from app.services.daily_prices import DailyPriceService
from app.services.indicators import IndicatorService
from app.services.stocks import StockService


class UsageError(ValueError):
    pass


_output_redactor = Redactor()


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error includes untrusted values, including unknown arguments.
        raise UsageError("Invalid CLI arguments; use --help")


def parser():
    result = SafeParser(description="Local market-data collection; no coverage guarantee")
    result.add_argument("--max-attempts", type=int, default=3)
    result.add_argument("--retry-delay", type=float, default=1.0)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("stocks", help="Synchronize the complete stock identity snapshot")
    daily = commands.add_parser("daily", help="Collect explicit stock/date scopes")
    daily.add_argument("--symbol", action="append", required=True)
    daily.add_argument("--start", type=date.fromisoformat, required=True)
    daily.add_argument("--end", type=date.fromisoformat, required=True)
    daily.add_argument(
        "--job-type", choices=("full", "incremental", "backfill"), default="backfill"
    )
    indicators = commands.add_parser(
        "indicators", help="Rebuild local indicators without fetching market data"
    )
    indicators.add_argument("--symbol", required=True)
    resume = commands.add_parser("resume", help="Replay one failed or interrupted job by ID")
    resume.add_argument("job_id", type=UUID)
    jobs = commands.add_parser("jobs", help="Inspect recent jobs and find interrupted IDs")
    jobs.add_argument("--limit", type=int, default=20)
    return result


def _emit(kind, **values):
    payload = json.loads(json.dumps({"event": kind, **values}, default=str))
    print(json.dumps(_output_redactor.value(payload), ensure_ascii=False))


def _job(job):
    _emit("job_result", **asdict(job), coverage_verified=False)


def main(argv=None) -> int:
    global _output_redactor
    engine = None
    try:
        args = parser().parse_args(argv)
        retry = RetryPolicy(args.max_attempts, args.retry_delay)
        scopes = []
        if args.command == "daily":
            if len(args.symbol) > 500:
                raise UsageError()
            scopes = [
                validate_scope(JobScope("akshare", args.job_type, symbol, args.start, args.end))
                for symbol in args.symbol
            ]
            if len({scope.symbol for scope in scopes}) != len(scopes):
                raise UsageError()
        if args.command == "jobs" and not 1 <= args.limit <= 100:
            raise UsageError()
        if args.command == "indicators":
            normalize_symbol(args.symbol)
        # All shared arguments are checked before engine/provider initialization or any writes.
        settings = load_settings()
        _output_redactor = configure_logging(settings)
        engine = create_configured_database_engine(settings)
        jobs = SyncJobRepository(engine)
        if args.command == "jobs":
            for job in jobs.list_recent(args.limit):
                _job(job)
            return 0
        sessions = create_session_factory(engine)
        if args.command == "indicators":
            symbol = normalize_symbol(args.symbol)
            with jobs.ownership():
                changed = IndicatorService.rebuild(sessions, symbol)
            _emit(
                "indicator_result",
                symbol=symbol,
                changed_count=changed,
                calculation_version=CALCULATION_VERSION,
                coverage_verified=False,
            )
            return 0
        runner = CollectionRunner(
            jobs,
            StockService(sessions),
            DailyPriceService(sessions),
            AkShareProvider(settings),
            retry=retry,
        )
        results = []
        if args.command == "stocks":
            results.append(runner.run(JobScope("akshare", "full")))
            _job(results[-1])
        elif args.command == "resume":
            results.append(runner.resume(args.job_id))
            _job(results[-1])
        else:
            for scope in scopes:
                results.append(runner.run(scope))
                _job(results[-1])
        failed = sum(result.status != "succeeded" for result in results)
        status = "failed" if failed == len(results) else "partial" if failed else "succeeded"
        _emit(
            "collection_summary",
            status=status,
            job_count=len(results),
            failed_jobs=failed,
            coverage_verified=False,
        )
        return 1 if failed else 0
    except (UsageError, MarketDataValidationError, ConfigurationError):
        _emit("cli_error", code="invalid_collection_arguments_or_configuration")
        return 2
    except ApplicationError as error:
        _emit("cli_error", code=error.code)
        return 2 if error.code in {"invalid_retry_policy", "invalid_job_scope"} else 1
    except SQLAlchemyError:
        _emit("cli_error", code="collection_storage_error")
        return 1
    except KeyboardInterrupt:
        _emit(
            "cli_error", code="collection_interrupted", recovery="inspect jobs, then resume by ID"
        )
        return 130
    except Exception:
        _emit("cli_error", code="collection_internal_error")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


def _terminate(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _terminate)
    raise SystemExit(main())
