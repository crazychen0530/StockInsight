"""Health endpoint response contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """API process liveness response without dependency health claims."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    version: str
