"""Explicitly authorized, bounded business trial through the existing TLS/auth proxy."""

import argparse
import base64
import email
import hashlib
import json
import os
import re
import signal
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def sanitize_line(line, secrets):
    # Empty credentials in anonymous mode must not corrupt the protocol/log text.
    for value in secrets:
        if value:
            line = line.replace(value, "<redacted>")
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1<redacted>@", line)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=28800)
    parser.add_argument(
        "--anonymous",
        action="store_true",
        help="Use the separate read-only public proxy on localhost:18843",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Validate the separate local origin only; never start a tunnel",
    )
    args = parser.parse_args()
    if not 60 <= args.duration <= 86400:
        parser.error("Trial must last 60..86400 seconds")
    expected = "d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db"
    if hashlib.sha256(args.binary.read_bytes()).hexdigest() != expected:
        parser.error("Unverified cloudflared binary")
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    ca = Path(
        "data/runtime/public-ca.crt"
        if args.anonymous
        else "secrets/production/local-ca.crt"
    ).resolve()
    local_tls = ssl.create_default_context(cafile=str(ca))
    public_tls = ssl.create_default_context()
    # Existing owner's invitation; never printed, persisted or passed on the CLI.
    password = (
        ""
        if args.anonymous
        else Path("secrets/production/preview_password").read_text().strip()
    )
    auth = "Basic " + base64.b64encode(f"preview:{password}".encode()).decode()
    state = {
        "origin": "https://localhost:18843"
        if args.anonymous
        else "https://localhost:18443",
        "anonymous": args.anonymous,
        "registered": False,
        "url": None,
    }

    def save():
        temp = args.output / "state.new"
        temp.write_text(json.dumps(state, indent=2))
        temp.replace(args.output / "state.json")

    def request(base, path, authenticated=False, method="GET", spoof=False):
        headers = {"Cache-Control": "no-cache"}
        if authenticated:
            headers["Authorization"] = auth
        if spoof:
            headers.update(
                {
                    "X-Forwarded-For": "127.0.0.1",
                    "X-Forwarded-Proto": "http",
                    "CF-Connecting-IP": "127.0.0.1",
                    "X-Admin-Token": "invalid",
                }
            )
        req = urllib.request.Request(base + path, headers=headers, method=method)
        context = local_tls if base == state["origin"] else public_tls
        state["last_probe_path"] = path
        save()
        for attempt in range(3):
            try:
                if args.anonymous and base != state["origin"]:
                    # Direct, bounded probe: inherited development proxies were intermittently
                    # disconnecting these public requests. TLS verification stays enabled.
                    command = [
                        "/usr/bin/curl",
                        "--silent",
                        "--show-error",
                        "--ipv4",
                        "--include",
                        "--noproxy",
                        "*",
                        "--max-time",
                        "20",
                        "--connect-timeout",
                        "5",
                        "--request",
                        method,
                        base + path,
                    ]
                    for key, value in headers.items():
                        command.extend(["--header", key + ": " + value])
                    try:
                        result = subprocess.run(
                            command, capture_output=True, timeout=25, check=False
                        )
                    except subprocess.TimeoutExpired:
                        state["last_curl_exit"] = "subprocess_timeout"
                        raise OSError("Bounded direct HTTPS probe timed out") from None
                    if result.returncode:
                        state["last_curl_exit"] = result.returncode
                        raise OSError("Bounded direct HTTPS probe failed")
                    head, separator, body = result.stdout.partition(b"\r\n\r\n")
                    if not separator:
                        raise OSError("Invalid HTTPS probe response")
                    first, _, header_lines = head.partition(b"\r\n")
                    return (
                        int(first.split()[1]),
                        body,
                        email.message_from_bytes(header_lines),
                    )
                handlers = [NoRedirect(), urllib.request.HTTPSHandler(context=context)]
                if base == state["origin"]:
                    handlers.append(urllib.request.ProxyHandler({}))
                try:
                    response = urllib.request.build_opener(*handlers).open(
                        req, timeout=10
                    )
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    content = response.read()
                    return response.status, content, response.headers
            except OSError as error:
                state["last_transport_error_type"] = type(error).__name__
                save()
                if attempt == 2:
                    raise
                time.sleep(1)

    process = None
    reader = None
    try:
        assert request(state["origin"], "/")[0] == (200 if args.anonymous else 401)
        assert (
            request(state["origin"], "/api/v1/stocks?page_size=1", not args.anonymous)[
                0
            ]
            == 200
        )
        if args.local_only:
            if not args.anonymous:
                parser.error(
                    "Local-only validation requires the separate anonymous proxy"
                )
            checks = []
            cases = [
                ("/", 200),
                ("/stocks", 200),
                ("/source-settings", 200),
                ("/api/v1/health", 200),
                ("/api/v1/stocks?page_size=1", 200),
                (
                    "/api/v1/stocks/600519.SH/prices?start_date=2026-01-01&end_date=2026-10-12",
                    200,
                ),
                (
                    "/api/v1/stocks/600519.SH/indicators?start_date=2026-01-01&end_date=2026-10-12",
                    200,
                ),
                ("/api/v1/system/data-status", 200),
                ("/.env", 404),
                ("/docs", 404),
                ("/redoc", 404),
                ("/openapi.json", 404),
                ("/api/admin", 404),
            ]
            for path, expected_status in cases:
                status, body, headers = request(state["origin"], path)
                assert status == expected_status, "Local route gate failed"
                assert "WWW-Authenticate" not in headers, (
                    "Anonymous route prompted login"
                )
                if path.startswith("/api/") and status == 200:
                    json.loads(body)
                checks.append({"path": path, "status": status})
            for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"):
                status = request(
                    state["origin"],
                    "/api/v1/system/source-policy",
                    method=method,
                    spoof=True,
                )[0]
                assert status == 403, "Local method gate failed"
                checks.append({"method": method, "status": status})
            (args.output / "gates.json").write_text(json.dumps(checks, indent=2))
            state["local_only"] = True
            state["gates_passed"] = True
            save()
            print("独立匿名入口本地19项检查通过；没有启动任何公网Tunnel。", flush=True)
            return
        with tempfile.TemporaryDirectory(
            prefix="stockinsight-business-tunnel-home-"
        ) as home:
            env = {"HOME": home, "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
            for key in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
                if key in os.environ:
                    env[key] = os.environ[key]
            command = [
                str(args.binary.resolve()),
                "--no-autoupdate",
                "tunnel",
                "--url",
                state["origin"],
                "--http-host-header",
                "localhost",
                "--origin-server-name",
                "localhost",
                "--origin-ca-pool",
                str(ca),
                "--protocol",
                "quic",
                "--metrics",
                "127.0.0.1:0",
                "--edge-ip-version",
                "auto",
            ]
            process = subprocess.Popen(
                command,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            state["pid"] = process.pid
            started = time.monotonic()
            state["expires_at"] = (
                datetime.now(UTC) + timedelta(seconds=args.duration)
            ).isoformat()
            save()
            ready = threading.Event()

            def collect():
                with (args.output / "cloudflared.log").open("w") as log:
                    for line in process.stdout:
                        line = sanitize_line(
                            line,
                            [
                                password,
                                auth,
                                *(
                                    env.get(key, "")
                                    for key in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY")
                                ),
                            ],
                        )
                        log.write(line)
                        log.flush()
                        match = re.search(
                            r"https://[a-z0-9-]+\.trycloudflare\.com", line
                        )
                        if match:
                            state["url"] = match[0]
                        if "Registered tunnel connection" in line:
                            state["registered"] = True
                            ready.set()

            reader = threading.Thread(target=collect, daemon=True)
            reader.start()
            if not ready.wait(90) or not state["url"]:
                raise RuntimeError("Tunnel did not register")
            # Fail closed: any failed gate terminates this owned tunnel immediately.
            for attempt in range(5):
                try:
                    if request(state["url"], "/")[0] == (
                        200 if args.anonymous else 401
                    ):
                        break
                except OSError:
                    pass
                time.sleep(2)
            gates = []

            def retain():
                (args.output / "gates.json").write_text(json.dumps(gates, indent=2))

            if not args.anonymous:
                for path in (
                    "/",
                    "/stocks",
                    "/source-settings",
                    "/data-status",
                    "/api/v1/health",
                    "/api/v1/stocks",
                    "/api/v1/system/source-policy",
                    "/docs",
                    "/redoc",
                    "/openapi.json",
                    "/.env",
                    "/assets/missing.js",
                ):
                    status = request(state["url"], path)[0]
                    gates.append(
                        {
                            "path": path,
                            "authenticated": False,
                            "status": status,
                            "expected": 401,
                        }
                    )
                    retain()
                    assert status == 401, "Unauthenticated gate failed"
                spoof_status = request(state["url"], "/api/v1/stocks", spoof=True)[0]
                gates.append(
                    {
                        "path": "/api/v1/stocks",
                        "spoofed_headers": True,
                        "status": spoof_status,
                        "expected": [401, 403],
                    }
                )
                retain()
                assert spoof_status in (401, 403), (
                    "Spoofed unauthenticated request was not denied"
                )
            for path, expected_status in (
                ("/", 200),
                ("/stocks", 200),
                ("/guide", 200),
                ("/api/v1/stocks?page_size=1", 200),
                (
                    "/api/v1/stocks/600519.SH/prices?start_date=2026-01-01&end_date=2026-10-12",
                    200,
                ),
                (
                    "/api/v1/stocks/600519.SH/indicators?start_date=2026-01-01&end_date=2026-10-12",
                    200,
                ),
                ("/api/v1/system/data-status", 200),
                ("/docs", 404),
                ("/openapi.json", 404),
            ):
                status, body, headers = request(state["url"], path, not args.anonymous)
                gates.append(
                    {
                        "path": path,
                        "authenticated": not args.anonymous,
                        "status": status,
                        "expected": expected_status,
                    }
                )
                retain()
                assert status == expected_status, "Authenticated gate failed"
                assert "localhost" not in headers.get("Location", ""), (
                    "Origin redirect leaked"
                )
                if path.startswith("/api/") and status == 200:
                    json.loads(body)
            for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"):
                status = request(
                    state["url"],
                    "/api/v1/system/source-policy",
                    not args.anonymous,
                    method,
                )[0]
                gates.append(
                    {
                        "path": "/api/v1/system/source-policy",
                        "method": method,
                        "status": status,
                        "expected": [403, 405] if method == "TRACE" else 403,
                    }
                )
                retain()
                assert status in ((403, 405) if method == "TRACE" else (403,)), (
                    "Write/method gate failed"
                )
            if args.anonymous:
                for path in ("/.env", "/api/admin", "/api/v1/unknown", "/redoc"):
                    status = request(state["url"], path)[0]
                    gates.append({"path": path, "status": status, "expected": 404})
                    retain()
                    assert status == 404, "Private/unknown route was accessible"
            state["gates_passed"] = True
            save()
            print(json.dumps(state), flush=True)
            print(
                f"公网地址：{state['url']}\n到期时间（北京时间）：{datetime.fromisoformat(state['expires_at']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')}\n提前关闭：./stockinsight.sh public-stop 或 Ctrl+C",
                flush=True,
            )
            while time.monotonic() - started < args.duration:
                if process.poll() is not None or (args.output / "STOP").exists():
                    break
                time.sleep(1)
    except (OSError, ValueError, AssertionError, RuntimeError) as error:
        state["failure_type"] = type(error).__name__
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if reader:
            reader.join(timeout=5)
        state["process_stopped"] = process is None or process.poll() is not None
        save()
        print(json.dumps({"process_stopped": state["process_stopped"]}), flush=True)


if __name__ == "__main__":

    def interrupt(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        main()
    except (OSError, ValueError, AssertionError, RuntimeError, KeyboardInterrupt):
        raise SystemExit(
            "Business trial stopped; see sanitized state and gates"
        ) from None
