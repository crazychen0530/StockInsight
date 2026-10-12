"""Failure-boundary tests for operational logic; no live services or credentials."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from deploy import operations
from deploy.scheduler_entrypoint import arguments


def test_calendar_cutoff_and_outside_coverage():
    calendar = {
        "coverage_start": "2026-01-01",
        "coverage_end": "2026-12-31",
        "trading_dates": ["2026-10-09", "2026-10-12"],
    }
    assert (
        operations.target_day(calendar, datetime(2026, 10, 12, 10, 29, tzinfo=UTC))
        == "2026-10-09"
    )
    assert (
        operations.target_day(calendar, datetime(2026, 10, 12, 10, 30, tzinfo=UTC))
        == "2026-10-12"
    )
    assert (
        operations.target_day(calendar, datetime(2026, 10, 11, 15, tzinfo=UTC))
        == "2026-10-09"
    )
    with pytest.raises(ValueError):
        operations.target_day(calendar, datetime(2027, 1, 1, tzinfo=UTC))


def test_retention_keeps_daily_weekly_and_ignores_unrelated_files():
    latest = datetime(2026, 10, 12, 12, tzinfo=UTC)
    paths = [
        Path(
            f"stockinsight-{(latest - timedelta(days=i)).strftime('%Y%m%dT%H%M%SZ')}-ab12.dump.gpg"
        )
        for i in range(42)
    ]
    keep = operations.retained_archives([*paths, Path("customer.dump.gpg")])
    assert set(paths[:7]) <= keep
    assert paths[-1] not in keep
    assert Path("customer.dump.gpg") not in keep
    assert 7 <= len(keep) <= 11


def test_restore_refuses_live_or_nonempty_database(monkeypatch):
    monkeypatch.setenv("PGDATABASE", "stockinsight")
    with pytest.raises(ValueError, match="independent"):
        operations.restore(Path("irrelevant"))
    monkeypatch.setenv("PGDATABASE", "stockinsight_restore")
    monkeypatch.setattr(operations, "query", lambda _: {"tables": 4})
    with pytest.raises(ValueError, match="empty"):
        operations.restore(Path("irrelevant"))


@pytest.mark.parametrize(
    "destination",
    ["", "host:/dir", "user@host:/dir/../other", "user@host:/dir;touch x"],
)
def test_transfer_rejects_unsafe_or_missing_destination(destination):
    with pytest.raises(ValueError):
        operations.transfer(Path("backup"), "0" * 64, destination)


def test_scheduler_universe_validates_bounds_and_builds_existing_cli(tmp_path):
    path = tmp_path / "scheduler.json"
    path.write_text(
        json.dumps({"symbols": ["600519.SH"], "initial_start": "2026-01-05"})
    )
    args = arguments(path)
    assert args[-2:] == ["--symbol", "600519.SH"]
    assert "--catch-up" in args
    for symbols in [
        [],
        ["600519.SH"] * 2,
        ["600519.SH;bad"],
        [str(i) for i in range(101)],
    ]:
        path.write_text(json.dumps({"symbols": symbols, "initial_start": "2026-01-05"}))
        with pytest.raises(ValueError):
            arguments(path)


def test_atomic_status_replaces_complete_json(tmp_path):
    path = tmp_path / "state.json"
    operations.atomic_json(path, {"remote_verified": False})
    operations.atomic_json(path, {"remote_verified": True})
    assert json.loads(path.read_text()) == {"remote_verified": True}
    assert path.stat().st_mode & 0o077 == 0
    assert not list(tmp_path.glob("*.partial"))


def test_traffic_window_counts_server_errors_and_p95(tmp_path):
    now = datetime(2026, 10, 12, tzinfo=UTC)
    path = tmp_path / "access.json"
    rows = [
        {
            "ts": now.timestamp(),
            "duration": value / 1000,
            "status": 500 if value == 900 else 200,
        }
        for value in range(100, 1001, 100)
    ]
    rows.append({"ts": now.timestamp() - 400, "duration": 100, "status": 500})
    path.write_text("partial line\n" + "\n".join(json.dumps(row) for row in rows))
    assert operations.traffic_metrics(path, now) == {
        "requests": 10,
        "p95_ms": 1000.0,
        "error_percent": 10.0,
    }


def test_remote_checksum_mismatch_never_promotes_archive(monkeypatch, tmp_path):
    from types import SimpleNamespace

    commands = []
    original = operations.shutil.copyfile
    monkeypatch.setattr(
        operations.shutil,
        "copyfile",
        lambda source, target: Path(target).write_text("fixture-key"),
    )

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout="wrong-checksum  archive.partial\n")

    monkeypatch.setattr(operations.subprocess, "run", run)
    with pytest.raises(ValueError, match="checksum"):
        operations.transfer(
            tmp_path / "archive.dump.gpg", "0" * 64, "backup@example.com:/archive"
        )
    assert len(commands) == 2
    assert not any("mv -n" in str(part) for command in commands for part in command)
    monkeypatch.setattr(operations.shutil, "copyfile", original)
