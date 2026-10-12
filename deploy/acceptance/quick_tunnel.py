"""Bounded Quick Tunnel test exposing only an isolated static loopback HTTP handler.

No application imports, database connections, production configuration or credentials.
The binary is supplied explicitly; no installation, login or system service changes.
"""

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--protocol", choices=("quic", "http2"), default="quic")
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 10 <= args.duration <= 600:
        parser.error("Duration must be between 10 and 600 seconds")
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    test_id = uuid4().hex
    body = json.dumps(
        {
            "service": "isolated-quick-tunnel-test",
            "test_id": test_id,
            "stockinsight_connected": False,
        }
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path not in ("/", "/health"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state = {
        "port": port,
        "test_id": test_id,
        "protocol": args.protocol,
        "url": None,
        "registered": False,
    }
    process = None
    reader = None
    ready = threading.Event()
    proxy_secrets = []
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        value = os.environ.get(name, "")
        if value:
            proxy_secrets.append(value)
            proxy_secrets.extend(
                unquote(part)
                for part in (urlsplit(value).username, urlsplit(value).password)
                if part and len(part) > 4
            )

    def save():
        target = args.output / "state.json"
        temporary = args.output / "state.new"
        temporary.write_text(json.dumps(state, indent=2))
        os.replace(temporary, target)

    def collect():
        with (args.output / "cloudflared.log").open("w") as log:
            for line in process.stdout:
                for value in proxy_secrets:
                    line = line.replace(value, "<redacted>")
                line = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1<redacted>@", line)
                line = re.sub(
                    r"(?i)((?:token|password|tunnelSecret)=)[^\s]+",
                    r"\1<redacted>",
                    line,
                )
                log.write(line)
                log.flush()
                match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                if match:
                    state["url"] = match[0]
                if "Registered tunnel connection" in line:
                    state["registered"] = True
                    ready.set()

    try:
        with tempfile.TemporaryDirectory(prefix="stockinsight-tunnel-home-") as home:
            environment = {"HOME": home, "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
            # Only ordinary outbound proxy configuration is inherited, never application env.
            for name in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
                if name in os.environ:
                    environment[name] = os.environ[name]
            command = [
                str(args.binary.resolve()),
                "--no-autoupdate",
                "tunnel",
                "--url",
                f"http://127.0.0.1:{port}",
                "--protocol",
                args.protocol,
                "--metrics",
                "127.0.0.1:0",
                "--edge-ip-version",
                "auto",
            ]
            process = subprocess.Popen(
                command,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            state["pid"] = process.pid
            save()
            reader = threading.Thread(target=collect, daemon=True)
            reader.start()
            start = time.monotonic()
            while time.monotonic() - start < min(90, args.duration):
                if (
                    ready.wait(1)
                    or process.poll() is not None
                    or (args.output / "STOP").exists()
                ):
                    break
            save()
            if not state["registered"] or not state["url"]:
                state["result"] = "no_registered_connection"
                return 1
            print(
                json.dumps(
                    {
                        "url": state["url"],
                        "port": port,
                        "protocol": args.protocol,
                        "test_id": test_id,
                        "stop_file": str(args.output / "STOP"),
                    }
                ),
                flush=True,
            )
            # A host-side HTTPS check does not replace the user's external browser check.
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(
                        state["url"] + "/?probe=" + test_id, timeout=10
                    ) as response:
                        state["https_status"] = response.status
                        state["https_body_matches"] = response.read() == body
                    state["tls_verified"] = True
                    break
                except OSError as error:
                    state["https_error_type"] = type(error).__name__
                    time.sleep(2)
            save()
            while time.monotonic() - start < args.duration:
                if process.poll() is not None or (args.output / "STOP").exists():
                    break
                time.sleep(1)
            state["result"] = "connected_then_stopped"
            return int(not state.get("https_body_matches"))
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
        server.shutdown()
        server.server_close()
        state["process_stopped"] = process is None or process.poll() is not None
        with socket.socket() as probe:
            probe.settimeout(2)
            state["local_port_closed"] = probe.connect_ex(("127.0.0.1", port)) != 0
        save()
        print(
            json.dumps(
                {
                    "process_stopped": state["process_stopped"],
                    "local_port_closed": state["local_port_closed"],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":

    def interrupt(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (OSError, ValueError, KeyError):
        raise SystemExit(
            "Isolated tunnel test stopped; inspect sanitized evidence"
        ) from None
