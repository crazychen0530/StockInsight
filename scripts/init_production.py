"""Create private local production rehearsal config; never overwrite existing secrets."""

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("secrets/production"))
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--image-tag", default="m6-local")
    args = parser.parse_args()
    directory = args.directory.resolve()
    # Host directory 0700 protects bind-mounted 0444 files from other host users.
    # Compose file secrets cannot remap ownership; only selected files enter each container.
    os.umask(0o077)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    for role in ("admin", "owner", "api", "worker", "backup"):
        path = directory / f"{role}_password"
        if not path.exists():
            path.write_text(secrets.token_urlsafe(36) + "\n")
        path.chmod(0o444)
    for name in ("backup_key", "backup_ssh_key", "backup_known_hosts", "alert_url"):
        path = directory / name
        if not path.exists():
            path.write_text(
                secrets.token_urlsafe(48) + "\n" if name == "backup_key" else ""
            )
        path.chmod(0o444)
    if not (directory / "invited_users").exists():
        password = secrets.token_urlsafe(24)
        hashed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "--network",
                "none",
                "caddy:2.11.7-alpine",
                "caddy",
                "hash-password",
                "--algorithm",
                "bcrypt",
                "--bcrypt-cost",
                "12",
            ],
            input=password + "\n",
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        if not hashed.startswith("$2"):
            raise ValueError("Invalid password hash output")
        (directory / "invited_users").write_text(
            "basic_auth {\n  preview " + hashed + "\n}\n"
        )
        (directory / "preview_password").write_text(password + "\n")
    (directory / "invited_users").chmod(0o444)
    config = directory / "config"
    config.mkdir(exist_ok=True)
    config.chmod(0o755)
    policy = config / "source-settings"
    policy.mkdir(exist_ok=True)
    policy.chmod(0o755)
    settings = policy / "source-policy.json"
    # Match the repository's existing serialized policy shape.
    if not settings.exists():
        settings.write_text(
            json.dumps({"mode": "tencent", "revision": 0, "updated_at": None})
        )
    settings.chmod(0o444)
    schedule = config / "scheduler.json"
    if not schedule.exists():
        schedule.write_text(
            json.dumps(
                {
                    "symbols": ["000001.SZ", "600519.SH", "300750.SZ", "600036.SH"],
                    "initial_start": "2026-01-05",
                },
                indent=2,
            )
        )
    schedule.chmod(0o444)
    if not args.env_file.exists():
        args.env_file.write_text(
            f"PRODUCTION_PROJECT=stockinsight-m6\nPRODUCTION_SECRETS_DIR={directory}\n"
            f"PRODUCTION_CONFIG_DIR={config}\nAPP_IMAGE=stockinsight-production-app:{args.image_tag}\n"
            f"PROXY_IMAGE=stockinsight-production-proxy:{args.image_tag}\nOPS_IMAGE=stockinsight-production-ops:{args.image_tag}\n"
            "DOMAIN=localhost\nTLS_ISSUER=internal\nPROXY_BIND=127.0.0.1\nHTTP_PORT=18080\nHTTPS_PORT=18443\n"
            "CHECK_FRESHNESS=true\nBACKUP_REMOTE=\n"
        )
    print(
        "Private production rehearsal files ready; no credentials printed or services started"
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit(
            "Initialization failed; existing secrets retained, inspect local tooling"
        ) from None
