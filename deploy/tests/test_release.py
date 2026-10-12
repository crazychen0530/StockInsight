"""Public deployment must never silently inherit rehearsal settings."""

import pytest

from scripts.release_production import preflight


@pytest.mark.parametrize("domain", ["", "localhost", "research.invalid", "host.test"])
def test_public_release_requires_real_domain(domain):
    with pytest.raises(ValueError, match="real domain"):
        preflight({"DOMAIN": domain, "TLS_ISSUER": "owner@example.com"}, False)


def test_rollback_refuses_schema_change_before_writing_environment(
    monkeypatch, tmp_path
):
    import json
    import sys

    from scripts import rollback_production

    manifest = tmp_path / "release.json"
    manifest.write_text(
        json.dumps(
            {
                "previous_images": {
                    "APP_IMAGE": "sha256:old",
                    "PROXY_IMAGE": "sha256:oldproxy",
                },
                "revision_before": "0001",
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["rollback", str(manifest), "--env-file", str(tmp_path / ".env.production")],
    )
    monkeypatch.setattr(
        rollback_production.subprocess, "check_output", lambda *a, **k: "0002\n"
    )
    with pytest.raises(ValueError, match="Schema changed"):
        rollback_production.main()
    assert not list(tmp_path.glob(".env.production*"))


def test_rehearsal_requires_local_binding():
    values = {
        "DOMAIN": "localhost",
        "APP_IMAGE": "app:sha",
        "PROXY_IMAGE": "proxy:sha",
        "OPS_IMAGE": "ops:sha",
    }
    preflight(values, True)
    with pytest.raises(ValueError):
        preflight({**values, "PROXY_BIND": "0.0.0.0"}, True)


def test_public_release_rejects_local_ca_or_missing_offsite():
    values = {"DOMAIN": "localhost", "TLS_ISSUER": "internal"}
    with pytest.raises(ValueError, match="real domain"):
        preflight(values, False)
    with pytest.raises(ValueError, match="offsite"):
        preflight(
            {"DOMAIN": "research.example.com", "TLS_ISSUER": "owner@example.com"}, False
        )
