"""Regression guards for anonymous tunnel handshake parsing and secret-safe logging."""

import pytest

from deploy.acceptance import business_tunnel
from deploy.acceptance.business_tunnel import (
    PublicProbeError,
    failure_summary,
    sanitize_line,
    wait_public_ready,
)


def test_anonymous_empty_credentials_preserve_registration_and_url():
    line = "Registered tunnel connection https://example-test.trycloudflare.com"
    assert sanitize_line(line, ["", ""]) == line


def test_nonempty_password_and_proxy_userinfo_are_redacted():
    line = "password-unique https://user:private@proxy.example:443"
    redacted = sanitize_line(line, ["", "password-unique"])
    assert "password-unique" not in redacted
    assert "private" not in redacted
    assert "proxy.example:443" in redacted


@pytest.fixture
def startup_clock(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(business_tunnel.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        business_tunnel.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    return clock


def test_startup_recovers_after_dns_delay_and_edge_not_ready(startup_clock):
    results = iter([PublicProbeError(6), PublicProbeError(6), (530,), (200,)])
    records = []

    def probe():
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    wait_public_ready(
        probe, 200, lambda: True, lambda: False, lambda *v: records.append(v)
    )
    assert startup_clock[0] == 9
    assert records == [
        ("curl_exit", 6),
        ("curl_exit", 6),
        ("http_status", 530),
        ("http_status", 200),
    ]


def test_persistent_dns_failure_times_out(startup_clock):
    def probe():
        raise PublicProbeError(6)

    with pytest.raises(RuntimeError, match="timed out"):
        wait_public_ready(
            probe, 200, lambda: True, lambda: False, lambda *v: None, timeout=6
        )
    assert startup_clock[0] == 6


@pytest.mark.parametrize("code", [35, 60])
def test_tls_failure_is_not_retried(startup_clock, code):
    def probe():
        raise PublicProbeError(code)

    with pytest.raises(PublicProbeError):
        wait_public_ready(probe, 200, lambda: True, lambda: False, lambda *v: None)
    assert startup_clock[0] == 0


@pytest.mark.parametrize("status", [301, 401, 403, 404])
def test_unexpected_http_gate_is_not_retried(startup_clock, status):
    with pytest.raises(RuntimeError, match="Unexpected"):
        wait_public_ready(
            lambda: (status,), 200, lambda: True, lambda: False, lambda *v: None
        )
    assert startup_clock[0] == 0


@pytest.mark.parametrize("alive,stopped", [(False, False), (True, True)])
def test_exit_or_stop_aborts_before_probe(startup_clock, alive, stopped):
    def probe():
        pytest.fail("must not probe after stop or process exit")

    with pytest.raises(RuntimeError):
        wait_public_ready(probe, 200, lambda: alive, lambda: stopped, lambda *v: None)


def test_dns_diagnostic_is_actionable_and_excludes_raw_errors():
    summary = failure_summary({"last_curl_exit": 6, "raw": "https://user:secret@proxy"})
    assert "DNS" in summary
    assert "secret" not in summary


def test_authenticated_startup_transport_recovers(startup_clock):
    results = iter(
        [business_tunnel.urllib.error.URLError("temporary DNS failure"), (401,)]
    )

    def probe():
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    wait_public_ready(probe, 401, lambda: True, lambda: False, lambda *v: None)
    assert startup_clock[0] == 3


def test_authenticated_tls_failure_is_not_retried(startup_clock):
    def probe():
        raise business_tunnel.urllib.error.URLError(
            business_tunnel.ssl.SSLCertVerificationError("bad certificate")
        )

    with pytest.raises(business_tunnel.urllib.error.URLError):
        wait_public_ready(probe, 401, lambda: True, lambda: False, lambda *v: None)
    assert startup_clock[0] == 0
