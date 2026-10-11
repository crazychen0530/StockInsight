"""Public task status contains safe error codes, never stored raw errors."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ScopeResponse(BaseModel):
    source: str
    job_type: str
    symbol: str | None
    start_date: date | None
    end_date: date | None


class JobResponse(BaseModel):
    id: UUID
    scope: ScopeResponse
    status: Literal["pending", "running", "succeeded", "partial", "failed"]
    total_count: int
    success_count: int
    failure_count: int
    checkpoint_symbol: str | None
    checkpoint_date: date | None
    error_code: str | None
    started_at: datetime
    finished_at: datetime | None


class DataStatusResponse(BaseModel):
    items: list[JobResponse]
    limit: int
    coverage_verified: Literal[False] = False
