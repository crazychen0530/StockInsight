"""Deterministic simulated clocks/providers, no actual upstream or daemon."""

import json
from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.collectors.errors import ProviderError
from app.core.errors import ApplicationError
from app.jobs.scheduler import AfterCloseScheduler, ReadyProvider, TradingCalendar, main
from app.repositories.sync_jobs import JobScope
from tests.test_daily_price_service import END, START, FixtureDailyProvider, bar

CALENDAR = TradingCalendar(
    "fixture_simulated", date(2026, 9, 1), date(2026, 10, 31), frozenset({START, END})
)
NOW = datetime(2026, 9, 29, 9, 30, tzinfo=UTC)


def scheduler():
    repository, runner = MagicMock(), MagicMock()
    repository.scope.side_effect = lambda symbol, day, start: (
        JobScope("akshare", "incremental", symbol, START, day),
        None,
        False,
    )
    runner.run.return_value = SimpleNamespace(status="succeeded")
    return (
        AfterCloseScheduler(repository, runner, CALENDAR, ["000001.SZ", "000002.SZ"], START),
        repository,
        runner,
    )


def test_shanghai_before_after_close_holiday_and_coverage():
    assert not CALENDAR.due(NOW.replace(minute=29), time(17, 30))
    assert CALENDAR.due(NOW, time(17, 30))
    assert not CALENDAR.due(NOW.replace(day=30), time(17, 30))  # Explicit calendar holiday weekday.
    with pytest.raises(ApplicationError, match="coverage"):
        CALENDAR.due(NOW.replace(month=11), time(17, 30))
    with pytest.raises(ValueError):
        CALENDAR.due(NOW.replace(tzinfo=None), time(17, 30))


def test_no_provider_before_due_and_partial_success_continues():
    service, repo, runner = scheduler()
    assert service.tick(NOW.replace(hour=8))["status"] == "not_due"
    runner.run.assert_not_called()
    runner.run.side_effect = [SimpleNamespace(status="failed"), SimpleNamespace(status="succeeded")]
    assert service.tick(NOW) == {
        "status": "partial",
        "job_count": 2,
        "failed_jobs": 1,
        "skipped_jobs": 0,
    }
    assert runner.run.call_count == 2
    repo.ownership.assert_called_once()


def test_durable_completed_skips_and_failed_resumes_original_scope():
    service, repo, runner = scheduler()
    scope = JobScope("akshare", "incremental", "000002.SZ", START, END)
    repo.scope.side_effect = [(scope, None, True), (scope, "fixture-job-id", False)]
    result = service.tick(NOW)
    assert result["skipped_jobs"] == 1
    runner.run.assert_called_once_with(scope, resume_id="fixture-job-id")


def test_not_ready_and_calendar_conflicts_are_visible():
    provider = ReadyProvider(FixtureDailyProvider(), CALENDAR)
    with pytest.raises(ProviderError) as error:
        provider.fetch_daily_prices("000001.SZ", START, END)
    assert error.value.code == "daily_data_not_ready" and error.value.retryable
    provider = ReadyProvider(FixtureDailyProvider({"000001.SZ": (bar(day=END),)}), CALENDAR)
    assert provider.fetch_daily_prices("000001.SZ", START, END).records[0].trade_date == END
    provider = ReadyProvider(
        FixtureDailyProvider({"000001.SZ": (bar(day=END), bar(day=date(2026, 9, 30)))}), CALENDAR
    )
    with pytest.raises(ApplicationError, match="calendar"):
        provider.fetch_daily_prices("000001.SZ", START, END)


@pytest.mark.parametrize(
    "at,symbols",
    [(time(14), ["000001.SZ"]), (time(17), []), (time(17), ["000001.SZ", "000001.sz"])],
)
def test_invalid_configuration(at, symbols):
    with pytest.raises(ValueError):
        AfterCloseScheduler(None, None, CALENDAR, symbols, START, at=at)


def test_calendar_file_duplicate_and_safe_cli_failure(tmp_path, capsys):
    path = tmp_path / "calendar.json"
    value = {
        "source": "fixture_simulated",
        "coverage_start": "2026-09-01",
        "coverage_end": "2026-10-31",
        "trading_dates": ["2026-09-28"],
    }
    path.write_text(json.dumps(value))
    assert TradingCalendar.load(path).days == frozenset({START})
    value["trading_dates"].append("2026-09-28")
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        TradingCalendar.load(path)
    assert (
        main(
            [
                "--calendar",
                str(path),
                "--symbol",
                "000001.SZ",
                "--initial-start",
                "2026-09-28",
                "--once",
            ]
        )
        == 2
    )
    assert "invalid_scheduler_configuration" in capsys.readouterr().out


def test_catchup_uses_last_closed_day_and_advances_at_close():
    service, repo, runner = scheduler()
    before_close = NOW.replace(hour=8)
    assert CALENDAR.target_day(before_close, time(17, 30), catch_up=True) == START
    assert CALENDAR.target_day(NOW, time(17, 30), catch_up=True) == END
    assert CALENDAR.target_day(NOW.replace(day=30), time(17, 30), catch_up=True) == END
    assert CALENDAR.target_day(NOW.replace(day=1), time(17, 30), catch_up=True) is None
    service.tick(before_close, catch_up=True)
    assert all(call.args[1] == START for call in repo.scope.call_args_list)
    assert runner.run.call_count == 2
    with pytest.raises(ApplicationError):
        CALENDAR.target_day(NOW.replace(month=11), time(17, 30), catch_up=True)


def test_once_before_due_exits_without_fetching_or_waiting(monkeypatch, capsys):
    import app.jobs.scheduler as module

    monkeypatch.setattr(module.TradingCalendar, "load", lambda _: CALENDAR)
    monkeypatch.setattr(module, "datetime", SimpleNamespace(now=lambda _: NOW.replace(hour=8)))
    engine = MagicMock()
    monkeypatch.setattr(module, "create_configured_database_engine", lambda _: engine)
    constructor = MagicMock()
    monkeypatch.setattr(module, "CollectionRunner", constructor)
    assert (
        module.main(
            [
                "--calendar",
                "fixture-not-read.json",
                "--symbol",
                "000001.SZ",
                "--initial-start",
                START.isoformat(),
                "--once",
            ]
        )
        == 0
    )
    constructor.return_value.run.assert_not_called()
    engine.dispose.assert_called_once()
    assert '"status": "not_due"' in capsys.readouterr().out
