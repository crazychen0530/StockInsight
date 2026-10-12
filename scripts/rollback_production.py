"""Restore recorded previous application images only when database revision is unchanged."""

import argparse
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

if __package__:
    from .release_production import REVISION_QUERY, read_environment
else:
    from release_production import REVISION_QUERY, read_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    args = parser.parse_args()
    os.umask(0o077)
    manifest = json.loads(args.manifest.read_text())
    previous = manifest["previous_images"]
    if (
        not all(key in previous for key in ("APP_IMAGE", "PROXY_IMAGE"))
        or not manifest["revision_before"]
    ):
        raise ValueError("No previous release recorded")
    compose = [
        "docker",
        "compose",
        "--env-file",
        str(args.env_file),
        "-f",
        "compose.production.yaml",
    ]
    command = [
        "run",
        "--rm",
        "-T",
        "--no-deps",
        "migrate",
        "python",
        "-c",
        REVISION_QUERY,
    ]
    current = subprocess.check_output([*compose, *command], text=True).strip()
    if current != manifest["revision_before"]:
        raise ValueError("Schema changed; independent database recovery required")
    values = read_environment(args.env_file)
    values.update(previous)
    rollback_env = Path(str(args.env_file) + ".rollback-" + uuid4().hex[:8])
    with rollback_env.open("x") as output:
        output.write("".join(key + "=" + value + "\n" for key, value in values.items()))
    compose[3] = str(rollback_env)
    services = ["api", "proxy", "monitor"] + (
        ["scheduler"] if manifest.get("automation") else []
    )
    if manifest.get("operations"):
        services.append("backup")
    subprocess.run(
        [
            *compose,
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "120",
            *services,
        ],
        check=True,
    )
    subprocess.run(
        [
            *compose,
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/stocks?page_size=1',timeout=5)",
        ],
        check=True,
    )
    print(
        "Previous application images restored; private environment file:", rollback_env
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise SystemExit(
            "Rollback stopped; retain volumes and use the recorded recovery plan"
        ) from None
