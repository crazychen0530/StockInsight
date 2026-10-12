"""Bounded ten-reader journey sample over trusted local HTTPS, with one-second think time."""

import argparse
import base64
import json
import math
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--clients", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 900 or not 1 <= args.clients <= 10:
        parser.error("Maximum 900 seconds and 10 clients")
    directory = Path("secrets/production")
    symbols = json.loads((directory / "config/scheduler.json").read_text())["symbols"]
    credential = (
        "Basic "
        + base64.b64encode(
            ("preview:" + (directory / "preview_password").read_text().strip()).encode()
        ).decode()
    )
    context = ssl.create_default_context(cafile=str(directory / "local-ca.crt"))
    deadline = time.monotonic() + args.seconds

    def client(offset):
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=context),
        )
        samples = []
        index = offset
        while time.monotonic() < deadline:
            symbol = symbols[index % len(symbols)]
            index += 1
            paths = [
                "/stocks?query=&page=1&page_size=20",
                *[
                    f"/stocks/{symbol}/{resource}?start_date=2026-01-05&end_date=2026-10-09&limit=1000"
                    for resource in ("prices", "indicators")
                ],
            ]
            for path in paths:
                start = time.monotonic()
                try:
                    request = urllib.request.Request(
                        "https://localhost:18443/api/v1" + path,
                        headers={"Authorization": credential},
                    )
                    with opener.open(request, timeout=5) as response:
                        response.read()
                        status = response.status
                except urllib.error.HTTPError as error:
                    status = error.code
                except OSError:
                    status = 0
                samples.append(((time.monotonic() - start) * 1000, status))
            time.sleep(1)
        return samples

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.clients) as executor:
        samples = [
            sample
            for batch in executor.map(client, range(args.clients))
            for sample in batch
        ]
    successful = sorted(ms for ms, status in samples if status == 200)
    result = {
        "clients": args.clients,
        "universe": len(symbols),
        "seconds": round(time.monotonic() - start, 2),
        "requests": len(samples),
        "errors": sum(status != 200 for _, status in samples),
        "p95_ms": round(successful[math.ceil(len(successful) * 0.95) - 1], 2)
        if successful
        else None,
        "scope": "Loopback HTTPS + authentication, 3 API reads per journey, 1 second think time",
    }
    print(json.dumps(result, indent=2))
    return int(result["errors"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
