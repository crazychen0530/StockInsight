"""Regression guards for anonymous tunnel handshake parsing and secret-safe logging."""

from deploy.acceptance.business_tunnel import sanitize_line


def test_anonymous_empty_credentials_preserve_registration_and_url():
    line = "Registered tunnel connection https://example-test.trycloudflare.com"
    assert sanitize_line(line, ["", ""]) == line


def test_nonempty_password_and_proxy_userinfo_are_redacted():
    line = "password-unique https://user:private@proxy.example:443"
    redacted = sanitize_line(line, ["", "password-unique"])
    assert "password-unique" not in redacted
    assert "private" not in redacted
    assert "proxy.example:443" in redacted
