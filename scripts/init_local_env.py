"""Create a private Compose .env once, without printing or overwriting secrets."""

import os
import secrets
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / ".env"
    template = (root / ".env.example").read_text(encoding="utf-8")
    template = template.replace(
        "POSTGRES_PASSWORD=change-me-for-local-development",
        f"POSTGRES_PASSWORD={secrets.token_hex(24)}",
    )
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SystemExit(
            ".env already exists; left unchanged. Reuse or edit it locally."
        ) from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(template)
    print("Created private .env for local Compose; password is not displayed.")


if __name__ == "__main__":
    main()
