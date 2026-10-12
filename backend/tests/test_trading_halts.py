"""Reviewed finite halts, simulated calendar days; no actual upstream requests."""

import json
from datetime import date

import pytest

from app.jobs.trading_halts import TradingHalts


def registry(tmp_path, **updates):
    row = {
        "symbol": "000001.SZ",
        "start": "2026-09-29",
        "confirmed_through": "2026-09-30",
        "source_url": "https://www.szse.cn/fixture-simulated.pdf",
        "published_at": "2026-09-28",
        "verified_at": "2026-09-28",
    }
    row.update(updates)
    path = tmp_path / "halts.json"
    path.write_text(json.dumps({"version": 1, "records": [row]}))
    return path


def test_halt_only_affects_reviewed_symbol_and_interval_then_expires(tmp_path):
    halts = TradingHalts.load(registry(tmp_path))
    days = frozenset({date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 9)})
    assert halts.expected_day("000001.SZ", date(2026, 9, 30), days) == date(2026, 9, 28)
    assert halts.expected_day("000002.SZ", date(2026, 9, 30), days) == date(2026, 9, 30)
    assert halts.expected_day("000001.SZ", date(2026, 10, 9), days) == date(2026, 10, 9)
    assert (
        halts.expected_day("000001.SZ", date(2026, 9, 29), frozenset({date(2026, 9, 29)})) is None
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"confirmed_through": "2026-09-01"},
        {"confirmed_through": None},
        {"source_url": "https://szse.cn.example.test/fixture.pdf"},
        {"source_url": "http://www.szse.cn/fixture.pdf"},
        {"verified_at": "2026-09-01"},
    ],
)
def test_unconfirmed_unbounded_or_untrusted_registry_is_rejected(tmp_path, updates):
    with pytest.raises((ValueError, TypeError)):
        TradingHalts.load(registry(tmp_path, **updates))


def test_overlapping_records_are_rejected(tmp_path):
    path = registry(tmp_path)
    value = json.loads(path.read_text())
    value["records"].append(value["records"][0])
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Overlapping"):
        TradingHalts.load(path)
