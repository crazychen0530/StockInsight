"""Add/revoke proxy-only invited readers; private hashes and passwords never enter stdout."""

import argparse
import os
import re
import secrets
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("add", "revoke"))
    parser.add_argument("user")
    parser.add_argument("--directory", type=Path, default=Path("secrets/production"))
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", args.user):
        parser.error("Invalid reader name")
    path = args.directory / "invited_users"
    readers = dict(
        re.findall(r"^\s+([a-z][a-z0-9_-]*) (\$2\S+)$", path.read_text(), re.MULTILINE)
    )
    if args.action == "add":
        if args.user in readers:
            parser.error("Reader already exists; revoke before replacing")
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
                "--bcrypt-cost",
                "12",
            ],
            input=password + "\n",
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        if not hashed.startswith("$2"):
            raise ValueError("Invalid password hash")
        readers[args.user] = hashed
        password_file = args.directory / (args.user + "_password")
        private_temporary = password_file.with_suffix(".new")
        with private_temporary.open("x") as output:
            output.write(password + "\n")
        private_temporary.chmod(0o600)
        os.replace(private_temporary, password_file)
    else:
        if args.user not in readers:
            parser.error("Reader does not exist")
        if len(readers) == 1:
            parser.error(
                "Cannot revoke the final reader; replace access configuration explicitly"
            )
        del readers[args.user]
    temporary = path.with_suffix(".new")
    with temporary.open("x") as output:
        output.write(
            "basic_auth {\n"
            + "".join(
                f"  {name} {hashed}\n" for name, hashed in sorted(readers.items())
            )
            + "}\n"
        )
    temporary.chmod(0o444)
    os.replace(temporary, path)
    print(
        "Invitation configuration updated. Recreate ONLY the production proxy to apply it."
    )


if __name__ == "__main__":
    os.umask(0o077)
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit("Invitation update failed; no credentials printed") from None
