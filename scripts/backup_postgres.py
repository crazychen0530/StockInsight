"""Encrypt a local Compose PostgreSQL dump; never persist a plaintext archive."""

import argparse
import os
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.key_file.is_file() or args.key_file.stat().st_mode & 0o077:
        parser.error("Key file must exist with owner-only permissions")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects earlier backups; umask also protects the archive.
    os.umask(0o077)
    with args.output.open("xb") as target:
        dump = subprocess.Popen(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            encrypted = subprocess.run(
                [
                    "gpg",
                    "--batch",
                    "--pinentry-mode",
                    "loopback",
                    "--passphrase-file",
                    str(args.key_file),
                    "--symmetric",
                    "--cipher-algo",
                    "AES256",
                ],
                stdin=dump.stdout,
                stdout=target,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            dump.stdout.close()
            if dump.wait() or encrypted.returncode:
                raise RuntimeError("Encrypted backup failed; retain earlier backups")
        finally:
            if dump.poll() is None:
                dump.terminate()
                dump.wait()
    print("Encrypted backup completed:", args.output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError):
        raise SystemExit(
            "Backup failed; check Docker access, key permissions and output path"
        ) from None
