"""Initialize private local administration credentials without printing them."""

import os
import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    environment = root / ".env"
    content = environment.read_text()
    existing = [
        line.split("=", 1)[1].strip().strip("\"'")
        for line in content.splitlines()
        if line.startswith("LOCAL_ADMIN_TOKEN=")
    ]
    token = existing[-1] if existing and existing[-1] else secrets.token_urlsafe(32)
    if len(token) < 32:
        raise ValueError("Existing management token is too short")
    if not existing or not existing[-1]:
        content = "\n".join(
            line
            for line in content.splitlines()
            if not line.startswith("LOCAL_ADMIN_TOKEN=")
        )
        environment.write_text(content + "\nLOCAL_ADMIN_TOKEN=" + token + "\n")
    os.chmod(environment, 0o600)
    directory = root / "secrets"
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / "source-admin.token"
    if path.exists() and path.read_text().strip() != token:
        raise ValueError("Existing credential file differs; inspect manually")
    with open(
        path, "w", opener=lambda name, flags: os.open(name, flags, 0o600)
    ) as output:
        output.write(token + "\n")
    os.chmod(path, 0o600)
    (root / "data/source-settings").mkdir(parents=True, exist_ok=True)
    print(
        "Local source settings initialized; management token saved privately to secrets/source-admin.token"
    )


if __name__ == "__main__":
    main()
