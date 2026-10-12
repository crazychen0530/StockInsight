"""Small production backup/restore/monitor processes; no Docker socket or stored plaintext dump."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import signal
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.jobs.trading_halts import TradingHalts


def emit(event, **fields):
    print(
        json.dumps({"time": datetime.now(UTC).isoformat(), "event": event, **fields}),
        flush=True,
    )


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".partial")
    try:
        with temporary.open("x") as output:
            os.chmod(temporary, 0o600)
            json.dump(value, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def query(statement):
    # Read-only transaction and server-side timeout, with no credentials in argv/logs.
    result = subprocess.run(
        [
            "psql",
            "-XAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "BEGIN READ ONLY; SET LOCAL statement_timeout='10s'; "
            + statement
            + "; COMMIT;",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    for line in result.stdout.splitlines():
        if line.startswith(("{", "[")):
            return json.loads(line)
    raise ValueError("Database query returned no JSON result")


def retained_archives(paths):
    """Newest archive per each of the newest 7 dates and 4 ISO weeks, plus latest."""
    dates, weeks, kept = set(), set(), set()
    for path in sorted(paths, reverse=True):
        match = re.fullmatch(
            r"stockinsight-(\d{8}T\d{6}Z)-[a-f0-9]+\.dump\.gpg", path.name
        )
        if not match:
            continue
        stamp = datetime.strptime(match[1], "%Y%m%dT%H%M%SZ")
        day, week = stamp.date(), stamp.isocalendar()[:2]
        if (day not in dates and len(dates) < 7) or (
            week not in weeks and len(weeks) < 4
        ):
            kept.add(path)
        dates.add(day)
        weeks.add(week)
    return kept


def transfer(archive, digest, destination):
    # Restrict remote operands; no local shell and no arbitrary remote shell fragments.
    match = re.fullmatch(
        r"([A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+):(/[A-Za-z0-9_./-]+)", destination
    )
    if not match or ".." in match[2].split("/"):
        raise ValueError("Invalid SSH backup destination")
    host, directory = match.groups()
    target = directory.rstrip("/") + "/" + archive.name
    with tempfile.TemporaryDirectory() as temporary:
        key = Path(temporary) / "identity"
        shutil.copyfile("/run/secrets/backup_ssh_key", key)
        key.chmod(0o600)
        options = [
            "-i",
            str(key),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile=/run/secrets/backup_known_hosts",
            "-o",
            "ConnectTimeout=15",
        ]
        subprocess.run(
            ["scp", *options, str(archive), host + ":" + target + ".partial"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1800,
        )
        result = subprocess.run(
            ["ssh", *options, host, "sha256sum " + target + ".partial"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if not result.stdout.split() or result.stdout.split()[0] != digest:
            raise ValueError("Remote checksum mismatch")
        subprocess.run(
            ["ssh", *options, host, "mv -n " + target + ".partial " + target],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )


def backup(local_only=False):
    directory = Path(os.environ.get("BACKUP_DIRECTORY", "/backups"))
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".backup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive = directory / f"stockinsight-{stamp}-{uuid4().hex[:8]}.dump.gpg"
        partial = archive.with_suffix(archive.suffix + ".partial")
        start = time.monotonic()
        dump = None
        try:
            with tempfile.TemporaryDirectory() as home, partial.open("xb") as target:
                partial.chmod(0o600)
                dump = subprocess.Popen(
                    ["pg_dump", "-Fc", "--no-owner", "--no-acl"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    encrypted = subprocess.run(
                        [
                            "gpg",
                            "--homedir",
                            home,
                            "--batch",
                            "--pinentry-mode",
                            "loopback",
                            "--passphrase-file",
                            "/run/secrets/backup_key",
                            "--symmetric",
                            "--cipher-algo",
                            "AES256",
                        ],
                        stdin=dump.stdout,
                        stdout=target,
                        stderr=subprocess.DEVNULL,
                        timeout=1800,
                        check=False,
                    )
                    dump.stdout.close()
                    if dump.wait(timeout=30) or encrypted.returncode:
                        raise RuntimeError("Backup pipeline failed")
                    target.flush()
                    os.fsync(target.fileno())
                finally:
                    if dump.poll() is None:
                        dump.kill()
                        dump.wait()
            os.replace(partial, archive)
            with archive.open("rb") as encrypted_file:
                digest = hashlib.file_digest(encrypted_file, "sha256").hexdigest()
            if not local_only:
                transfer(archive, digest, os.environ.get("BACKUP_REMOTE", ""))
            receipt = {
                "time": datetime.now(UTC).isoformat(),
                "archive": archive.name,
                "bytes": archive.stat().st_size,
                "sha256": digest,
                "seconds": round(time.monotonic() - start, 3),
                "remote_verified": not local_only,
            }
            atomic_json(
                Path(os.environ.get("OPS_STATE", "/state")) / "backup-success.json",
                receipt,
            )
            if not local_only:
                kept = retained_archives(directory.glob("stockinsight-*.dump.gpg"))
                for old in directory.glob("stockinsight-*.dump.gpg"):
                    if old not in kept and re.fullmatch(
                        r"stockinsight-\d{8}T\d{6}Z-[a-f0-9]+\.dump\.gpg", old.name
                    ):
                        old.unlink()
            emit("backup_completed", **receipt)
            return receipt
        finally:
            partial.unlink(missing_ok=True)


def restore(archive):
    # A fresh, explicitly named restore DB is required; never restore into production.
    if not os.environ.get("PGDATABASE", "").endswith("_restore"):
        raise ValueError("Restore requires an independent _restore database")
    if query(
        "SELECT json_build_object('tables',count(*)) FROM pg_tables WHERE schemaname='public'"
    )["tables"]:
        raise ValueError("Restore target must be empty")
    start = time.monotonic()
    with tempfile.TemporaryDirectory() as home:
        decrypted = subprocess.Popen(
            [
                "gpg",
                "--homedir",
                home,
                "--batch",
                "--pinentry-mode",
                "loopback",
                "--passphrase-file",
                "/run/secrets/backup_key",
                "--decrypt",
                str(archive),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            restored = subprocess.run(
                [
                    "pg_restore",
                    "--exit-on-error",
                    "--single-transaction",
                    "--no-owner",
                    "--no-acl",
                    "-d",
                    os.environ["PGDATABASE"],
                ],
                stdin=decrypted.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1800,
                check=False,
            )
            decrypted.stdout.close()
            if decrypted.wait(timeout=30) or restored.returncode:
                raise RuntimeError("Restore pipeline failed")
        finally:
            if decrypted.poll() is None:
                decrypted.kill()
                decrypted.wait()
    emit("restore_completed", seconds=round(time.monotonic() - start, 3))


def target_day(calendar, now):
    local = now.astimezone(ZoneInfo("Asia/Shanghai"))
    day = local.date().isoformat()
    if not calendar["coverage_start"] <= day <= calendar["coverage_end"]:
        raise ValueError("Calendar coverage missing")
    eligible = [
        d
        for d in calendar["trading_dates"]
        if d < day or (d == day and (local.hour, local.minute) >= (18, 30))
    ]
    return max(eligible) if eligible else None


def notify(alerts):
    path = Path("/run/secrets/alert_url")
    endpoint = path.read_text().strip() if path.exists() else ""
    if not endpoint:
        emit("alert_delivery_unconfigured", alerts=alerts)
        return False
    if not endpoint.startswith("https://"):
        raise ValueError("Alert endpoint requires HTTPS")
    request = urllib.request.Request(
        endpoint,
        json.dumps({"service": "stockinsight", "alerts": alerts}).encode(),
        {"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status not in (200, 201, 202, 204):
            raise RuntimeError("Alert delivery failed")
    return True


def traffic_metrics(path, now):
    recent = []
    try:
        with Path(path).open("rb") as log:
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 1024 * 1024))
            lines = log.read().decode("utf-8", errors="replace").splitlines()
        for line in lines:
            try:
                item = json.loads(line)
                if item.get("ts", 0) >= now.timestamp() - 300 and "duration" in item:
                    recent.append(item)
            except ValueError:
                continue
    except OSError:
        return None
    if not recent:
        return None
    latencies = sorted(float(item["duration"]) * 1000 for item in recent)
    return {
        "requests": len(recent),
        "p95_ms": round(latencies[math.ceil(len(latencies) * 0.95) - 1], 2),
        "error_percent": round(
            sum(int(item["status"]) >= 500 for item in recent) / len(recent) * 100, 2
        ),
    }


def stale_symbols(rows, target, calendar, halts=None):
    """Require actual bars through the eligible session, including reviewed finite halts."""
    if not target:
        return []
    day = date.fromisoformat(target)
    days = frozenset(date.fromisoformat(value) for value in calendar["trading_dates"])
    stale = []
    for row in rows:
        expected = halts.expected_day(row["symbol"], day, days) if halts else day
        # Missing history is still stale; a halt never fabricates a data watermark.
        if (
            not row["latest"]
            or expected is None
            or date.fromisoformat(row["latest"]) < expected
        ):
            stale.append(row["symbol"])
    return stale


def monitor():
    now = datetime.now(UTC)
    alerts = []
    state = Path(os.environ.get("OPS_STATE", "/state"))
    try:
        with urllib.request.urlopen(
            "http://api:8000/api/v1/stocks?page_size=1", timeout=5
        ) as response:
            if response.status != 200:
                alerts.append("api_unavailable")
    except OSError:
        alerts.append("api_unavailable")
    try:
        calendar = json.loads(
            Path(os.environ.get("CALENDAR_FILE", "/config/calendar.json")).read_text()
        )
        target = target_day(calendar, now)
        days_left = (
            datetime.fromisoformat(calendar["coverage_end"]).date()
            - now.astimezone(ZoneInfo("Asia/Shanghai")).date()
        ).days
        if days_left < 30:
            alerts.append("calendar_expiring")
        scheduling = json.loads(
            Path(os.environ.get("SCHEDULER_FILE", "/config/scheduler.json")).read_text()
        )
        symbols = scheduling["symbols"]
        halt_path = scheduling.get("stock_halts_file")
        if halt_path is not None and halt_path != "/config/calendars/stock_halts.json":
            raise ValueError("Invalid reviewed stock halt file")
        halts = TradingHalts.load(halt_path) if halt_path else None
        if (
            not symbols
            or len(symbols) > 100
            or any(not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", s) for s in symbols)
        ):
            raise ValueError("Invalid universe")
        operands = ",".join("('" + symbol + "')" for symbol in symbols)
        rows = query(
            "SELECT coalesce(json_agg(row_to_json(t)),'[]'::json) FROM (SELECT u.symbol, max(p.trade_date)::text AS latest FROM (VALUES "
            + operands
            + ") AS u(symbol) LEFT JOIN daily_prices p USING(symbol) GROUP BY u.symbol) AS t"
        )
        if (
            os.environ.get("CHECK_FRESHNESS", "true") == "true"
            and target
            and stale_symbols(rows, target, calendar, halts)
        ):
            alerts.append("market_data_stale")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        alerts.append("database_or_calendar_check_failed")
    disk = shutil.disk_usage(os.environ.get("DISK_PATH", "/state"))
    disk_percent = round(disk.used / disk.total * 100, 2)
    if disk_percent >= 70:
        alerts.append("disk_usage_high")
    memory = {
        line.split(":")[0]: int(line.split()[1])
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith(("MemTotal:", "MemAvailable:"))
    }
    memory_percent = round((1 - memory["MemAvailable"] / memory["MemTotal"]) * 100, 2)
    if memory_percent >= 80:
        alerts.append("host_memory_high")
    try:
        receipt = json.loads((state / "backup-success.json").read_text())
        if not receipt["remote_verified"] or now - datetime.fromisoformat(
            receipt["time"]
        ) > timedelta(hours=26):
            alerts.append("offsite_backup_stale")
    except (OSError, ValueError, KeyError, TypeError):
        alerts.append("offsite_backup_missing")
    tls_host = os.environ.get("TLS_HOST", "")
    if tls_host:
        try:
            with (
                socket.create_connection((tls_host, 443), timeout=5) as connection,
                ssl.create_default_context().wrap_socket(
                    connection, server_hostname=tls_host
                ) as secured,
            ):
                expires = datetime.fromtimestamp(
                    ssl.cert_time_to_seconds(secured.getpeercert()["notAfter"]), UTC
                )
                if expires - now < timedelta(days=14):
                    alerts.append("tls_expiring")
        except (OSError, ValueError, KeyError):
            alerts.append("tls_check_failed")
    else:
        alerts.append("tls_monitor_unconfigured")
    traffic = traffic_metrics("/proxy-logs/access.json", now)
    if traffic and traffic["requests"] >= 10:
        if traffic["p95_ms"] > 500:
            alerts.append("proxy_latency_high")
        if traffic["error_percent"] >= 1:
            alerts.append("proxy_error_rate_high")
    result = {
        "traffic": traffic,
        "time": now.isoformat(),
        "alerts": alerts,
        "disk_percent": disk_percent,
        "host_memory_percent": memory_percent,
    }
    atomic_json(state / "monitor.json", result)
    emit("monitor_result", **result)
    if alerts:
        notify(alerts)
    return result


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("backup", "backup-loop", "restore", "monitor")
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Rehearsal only; does not prove offsite backup",
    )
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.command == "restore":
        if not args.archive:
            parser.error("Restore requires --archive")
        restore(args.archive)
        return 0
    while True:
        delay = 600
        try:
            if args.command.startswith("backup"):
                backup(args.local_only)
                delay = 86400
            else:
                result = monitor()
                if args.once:
                    return int(bool(result["alerts"]))
            if args.command == "backup" or args.once:
                return 0
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            RuntimeError,
            subprocess.SubprocessError,
        ):
            emit("operations_failed", operation=args.command)
            try:
                notify(
                    [
                        "backup_failed"
                        if args.command.startswith("backup")
                        else "monitor_failed"
                    ]
                )
            except (OSError, ValueError, RuntimeError):
                emit("alert_delivery_failed")
            if args.command == "backup" or args.once:
                return 1
            delay = 3600 if args.command == "backup-loop" else 600
        time.sleep(delay)


if __name__ == "__main__":

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0) from None
