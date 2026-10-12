"""Bounded, read-only loopback API sample; not a production capacity guarantee."""

import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

BASE_URL = "http://127.0.0.1:8000/api/v1"
PATHS = {
    "search": "/stocks?query=600519&page=1&page_size=20",
    "prices": "/stocks/600519.SH/prices?start_date=2026-01-05&end_date=2026-10-09&limit=1000",
    "indicators": (
        "/stocks/600519.SH/indicators?start_date=2026-01-05&end_date=2026-10-09&limit=1000"
    ),
    "status": "/system/data-status",
}


def request(path):
    start = time.perf_counter()

    # Ignore environment proxies and redirects: the benchmark stays on loopback.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(BASE_URL + path, timeout=5) as response:
            body = response.read()
            json.loads(body)
            ok = response.status == 200
            size = len(body)
    except (OSError, ValueError, urllib.error.URLError):
        ok, size = False, 0
    return (time.perf_counter() - start) * 1000, ok, size


def sample(concurrency):
    # Equal request mix, 80 measured requests per batch; 4 warmups are excluded.
    for path in PATHS.values():
        if not request(path)[1]:
            raise RuntimeError("Loopback API warmup failed")
    work = list(PATHS.items()) * 20
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        values = list(executor.map(lambda item: request(item[1]), work))
    duration = time.perf_counter() - start
    endpoints = {}
    for name in PATHS:
        selected = [
            value for (key, _), value in zip(work, values, strict=True) if key == name
        ]
        successful = sorted(ms for ms, ok, _ in selected if ok)
        endpoints[name] = {
            "requests": len(selected),
            "errors": sum(not ok for _, ok, _ in selected),
            "p50_ms": round(successful[math.ceil(len(successful) * 0.50) - 1], 2)
            if successful
            else None,
            "p95_ms": round(successful[math.ceil(len(successful) * 0.95) - 1], 2)
            if successful
            else None,
            "max_response_bytes": max(size for _, _, size in selected),
        }
    return {
        "concurrency": concurrency,
        "requests": len(work),
        "duration_seconds": round(duration, 3),
        "successful_requests_per_second": round(
            sum(ok for _, ok, _ in values) / duration, 2
        ),
        "endpoints": endpoints,
    }


def main():
    result = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Local development API, warm cache, no collection triggered, no user think time",
        "batches": [sample(concurrency) for concurrency in (1, 4, 10)],
    }
    print(json.dumps(result, indent=2))
    return int(
        any(
            endpoint["errors"]
            for batch in result["batches"]
            for endpoint in batch["endpoints"].values()
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
