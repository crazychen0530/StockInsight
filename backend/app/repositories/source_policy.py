"""Small local configuration store, independent of business database transactions."""

import fcntl
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import ApplicationError

PolicyMode = Literal["prefer_eastmoney", "eastmoney", "tencent"]


class SourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: PolicyMode = "prefer_eastmoney"
    revision: int = Field(default=0, ge=0, strict=True)
    updated_at: datetime | None = None


class SourcePolicyRepository:
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.path = self.directory / "source-policy.json"

    def read(self) -> SourcePolicy:
        try:
            return SourcePolicy.model_validate_json(self.path.read_text())
        except FileNotFoundError:
            if self.directory.is_dir():
                return SourcePolicy()
            raise ApplicationError(
                "source_policy_unavailable", "Source configuration unavailable", 503
            ) from None
        except (OSError, ValidationError):
            raise ApplicationError(
                "source_policy_unavailable", "Source configuration unavailable", 503
            ) from None

    def save(self, mode: PolicyMode, revision: int) -> SourcePolicy:
        temporary = None
        try:
            with (self.directory / ".write.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                old = self.read()
                if old.revision != revision:
                    raise ApplicationError(
                        "source_policy_conflict", "Reload source settings before saving", 409
                    )
                policy = SourcePolicy(
                    mode=mode, revision=revision + 1, updated_at=datetime.now(UTC)
                )
                with tempfile.NamedTemporaryFile(
                    mode="w", dir=self.directory, delete=False
                ) as output:
                    temporary = Path(output.name)
                    output.write(policy.model_dump_json())
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(temporary, 0o644)  # Non-secret; scheduler has a read-only mount.
                os.replace(temporary, self.path)
                return policy
        except OSError:
            raise ApplicationError(
                "source_policy_unavailable", "Source configuration unavailable", 503
            ) from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
