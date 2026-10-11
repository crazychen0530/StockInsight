"""Stable API error contract without raw request input or internal exceptions."""

from pydantic import BaseModel, ConfigDict


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: list[str | int]
    type: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str
    details: list[ValidationIssue] | None = None
