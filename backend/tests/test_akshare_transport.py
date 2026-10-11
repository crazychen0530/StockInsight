"""Offline subprocess integration with a fake SDK; never reaches market endpoints."""

import json
import logging
import os
import sys
from pathlib import Path

import pytest

from app.collectors._akshare_worker import main
from app.collectors.akshare import AkShareProvider
from app.collectors.akshare_transport import SubprocessAkShareTransport
from app.collectors.errors import ProviderContractError, ProviderError, ProviderTimeoutError
from app.core.config import Settings


@pytest.fixture
def fake_sdk(tmp_path, monkeypatch):
    package = tmp_path / "akshare.py"
    # Native SDK importing/printing/logging is intentionally noisy, simulating credentials.
    package.write_text("""
import logging
print("password=fixture-sdk-secret")
logging.warning("token=fixture-sdk-secret")
class Frame:
    columns = []
    def to_dict(self, **kwargs):
        return {"columns":["code","name"],"data":[["000001","模拟证券"]]}
def stock_info_a_code_name():
    print("password=fixture-sdk-secret")
    return Frame()
""")
    requests = tmp_path / "requests"
    requests.mkdir()
    (requests / "__init__.py").write_text("")
    (requests / "exceptions.py").write_text("class Timeout(Exception): pass\n")
    app_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([str(tmp_path), str(app_root)]))
    return package


def test_real_subprocess_maps_fake_sdk_and_suppresses_raw_output(fake_sdk, capsys):
    result = AkShareProvider(Settings(market_data_timeout_seconds=5)).fetch_stocks()
    assert result.records[0].symbol == "000001.SZ"
    assert "fixture-sdk-secret" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "body,error_type,code",
    [
        (
            "from requests.exceptions import Timeout; raise Timeout('token=fixture-secret')",
            ProviderTimeoutError,
            "provider_timeout",
        ),
        (
            "raise KeyError('password=fixture-secret')",
            ProviderContractError,
            "provider_contract_error",
        ),
        ("raise RuntimeError('password=fixture-secret')", ProviderError, "provider_unavailable"),
    ],
)
def test_real_sdk_failures_are_safe(fake_sdk, body, error_type, code, capsys):
    fake_sdk.write_text(f"def stock_info_a_code_name():\n    {body}\n")
    with pytest.raises(error_type) as failure:
        AkShareProvider(Settings(market_data_timeout_seconds=5)).fetch_stocks()
    assert failure.value.code == code
    assert "fixture-secret" not in str(failure.value) + capsys.readouterr().out


def test_actual_deadline_kills_and_reaps_sdk_child(fake_sdk, tmp_path, monkeypatch):
    pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("FIXTURE_CHILD_PID_PATH", str(pid_file))
    fake_sdk.write_text("""
import os
import time
from pathlib import Path
def stock_info_a_code_name():
    Path(os.environ["FIXTURE_CHILD_PID_PATH"]).write_text(str(os.getpid()))
    time.sleep(30)
""")
    with pytest.raises(ProviderTimeoutError):
        AkShareProvider(Settings(market_data_timeout_seconds=1)).fetch_stocks()
    assert pid_file.exists(), "Fixture child must have started before the deadline"
    pid = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_missing_optional_dependency_is_explicit(fake_sdk):
    fake_sdk.write_text("raise ImportError('password=fixture-secret')\n")
    with pytest.raises(ProviderError) as failure:
        AkShareProvider(Settings(market_data_timeout_seconds=5)).fetch_stocks()
    assert failure.value.code == "provider_dependency_missing"
    assert not failure.value.retryable


def test_private_worker_rejects_unknown_interface(fake_sdk):
    with pytest.raises(ProviderContractError):
        SubprocessAkShareTransport().call("unknown_interface", {}, 5)


def test_worker_preserves_native_date_and_decimal_mapping(monkeypatch, capsys):
    """Exercise actual DataFrame serialization without calling AKShare/network."""
    from datetime import date
    from types import SimpleNamespace

    pandas = pytest.importorskip("pandas", reason="optional market-data extra not installed")
    pytest.importorskip("requests")
    frame = pandas.DataFrame(
        [
            {
                "日期": date(2026, 9, 28),
                "股票代码": "000001",
                "开盘": 10.1,
                "最高": 1399.47,
                "最低": 9.8,
                "收盘": 10.25,
                "成交量": 12,
                "成交额": 12345.67,
            }
        ]
    )
    received = []

    def sdk_call(**kwargs):
        received.append(kwargs)
        return frame

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_zh_a_hist=sdk_call))
    from io import StringIO

    monkeypatch.setattr(
        sys,
        "stdin",
        StringIO(
            json.dumps(
                {"interface": "stock_zh_a_hist", "parameters": {"symbol": "000001", "adjust": ""}}
            )
        ),
    )
    previous_disable = logging.root.manager.disable
    try:
        assert main() == 0
    finally:
        logging.disable(previous_disable)
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"][0][0] == "2026-09-28"
    from decimal import Decimal

    exact = json.loads(json.dumps(payload), parse_float=Decimal)
    assert exact["data"][0][3] == Decimal("1399.47")
    assert exact["data"][0][7] == Decimal("12345.67")
    assert received == [{"symbol": "000001", "adjust": ""}]
