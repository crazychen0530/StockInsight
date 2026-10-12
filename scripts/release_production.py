"""Explicit production release, backup and migration orchestration; safe local rehearsal default."""

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

REVISION_QUERY = (
    "from sqlalchemy import text; "
    "from app.core.database import create_configured_database_engine; "
    "e=create_configured_database_engine(); c=e.connect(); "
    "print(c.scalar(text('SELECT version_num FROM alembic_version')) "
    "if c.scalar(text(\"SELECT to_regclass('public.alembic_version')\")) else '')"
)


def read_environment(path):
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#") and "=" in line
    )


def preflight(values, rehearsal):
    if rehearsal:
        if (
            values.get("PROXY_BIND", "127.0.0.1") != "127.0.0.1"
            or values.get("DOMAIN") != "localhost"
        ):
            raise ValueError("Rehearsal requires loopback and localhost")
    else:
        domain = values.get("DOMAIN", "")
        issuer = values.get("TLS_ISSUER", "")
        if (
            "@" not in issuer
            or "." not in domain
            or domain.endswith((".invalid", ".localhost", ".local", ".test"))
            or domain.startswith("localhost.")
        ):
            raise ValueError("Public deployment requires real domain and ACME contact")
        if (
            not values.get("BACKUP_REMOTE")
            or values.get("DATA_USE_CONFIRMED") != "true"
        ):
            raise ValueError(
                "Public deployment requires offsite backup and confirmed data use"
            )
        if not values.get("TLS_HOST"):
            raise ValueError("Public deployment requires external TLS monitoring host")
        secret = Path(values["PRODUCTION_SECRETS_DIR"])
        for name in ("alert_url", "backup_ssh_key", "backup_known_hosts"):
            if not (secret / name).read_text().strip():
                raise ValueError("Required operational secret is missing")
    if not all(values.get(name) for name in ("APP_IMAGE", "PROXY_IMAGE", "OPS_IMAGE")):
        raise ValueError("Explicit release images required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--rehearsal", action="store_true")
    parser.add_argument("--automation", action="store_true")
    parser.add_argument(
        "--operations",
        action="store_true",
        help="Start daily backup loop during rehearsal",
    )
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    values = read_environment(args.env_file)
    preflight(values, args.rehearsal)
    compose = [
        "docker",
        "compose",
        "--env-file",
        str(args.env_file),
        "-f",
        "compose.production.yaml",
    ]

    def run(*arguments):
        return subprocess.run([*compose, *arguments], check=True)

    run("config", "--quiet")
    if args.preflight_only:
        print("Production release preflight passed")
        return
    manifest = {
        "time": datetime.now(UTC).isoformat(),
        "rehearsal": args.rehearsal,
        "images": {},
        "previous_images": {},
        "revision_before": None,
        "automation": args.automation,
        "operations": args.operations or not args.rehearsal,
        "status": "prepared",
    }
    for key in ("APP_IMAGE", "PROXY_IMAGE", "OPS_IMAGE"):
        manifest["images"][key] = json.loads(
            subprocess.check_output(["docker", "image", "inspect", values[key]])
        )[0]["Id"]
    for service, key in (
        ("api", "APP_IMAGE"),
        ("proxy", "PROXY_IMAGE"),
        ("monitor", "OPS_IMAGE"),
    ):
        container = subprocess.check_output(
            [*compose, "ps", "-aq", service], text=True
        ).strip()
        if container:
            manifest["previous_images"][key] = json.loads(
                subprocess.check_output(["docker", "inspect", container])
            )[0]["Image"]
    run("up", "-d", "--wait", "--wait-timeout", "120", "db")
    run("run", "--rm", "--no-deps", "init-state")
    manifest["revision_before"] = subprocess.check_output(
        [
            *compose,
            "run",
            "--rm",
            "-T",
            "--no-deps",
            "migrate",
            "python",
            "-c",
            REVISION_QUERY,
        ],
        text=True,
    ).strip()
    target = Path("data/releases")
    target.mkdir(parents=True, exist_ok=True)
    receipt = target / (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8] + ".json"
    )
    # Retain previous image IDs before any schema/application mutation, including failed releases.
    receipt.write_text(json.dumps(manifest, indent=2))
    # Preserve the pre-migration state even on a fresh installation.
    backup = [
        "run",
        "--rm",
        "--no-deps",
        "backup",
        "python3",
        "/opt/operations.py",
        "backup",
    ]
    if args.rehearsal:
        backup.append("--local-only")
    run(*backup)
    run("run", "--rm", "--no-deps", "migrate")
    services = ["api", "proxy", "monitor"] + (["scheduler"] if args.automation else [])
    if manifest["operations"]:
        services.append("backup")
    run("up", "-d", "--wait", "--wait-timeout", "120", *services)
    run(
        "exec",
        "-T",
        "api",
        "python",
        "-c",
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/stocks?page_size=1', timeout=5)",
    )
    manifest["status"] = "completed"
    receipt.write_text(json.dumps(manifest, indent=2))
    print("Release receipt:", receipt)
    print(
        "Deployment steps passed; verify external HTTPS and core page before accepting release"
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, KeyError, ValueError, subprocess.SubprocessError):
        raise SystemExit(
            "Release stopped; retain current volumes, inspect step results and recorded previous images"
        ) from None
