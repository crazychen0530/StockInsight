"""Authenticated local configuration only; no HTTP market collection."""

import logging
import secrets
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ApplicationError
from app.repositories.source_policy import PolicyMode, SourcePolicy
from app.services.source_policy import SourcePolicyService

router = APIRouter(prefix="/system", tags=["system"])
logger = logging.getLogger("stockinsight.api.source_policy")


def service(request: Request):
    settings = request.app.state.settings
    if not settings.source_policy_directory:
        raise ApplicationError("source_policy_disabled", "Source settings are not enabled", 503)
    return SourcePolicyService(settings.source_policy_directory)


def authenticate(request: Request):
    settings = request.app.state.settings
    supplied = request.headers.get("x-admin-token", "")
    origin = request.headers.get("origin", "")
    allowed = {"http://localhost:5173", "http://127.0.0.1:5173"}
    local = urlsplit(str(request.url)).hostname in {"localhost", "127.0.0.1"}
    expected = settings.local_admin_token.get_secret_value() if settings.local_admin_token else ""
    if (
        settings.app_env != "development"
        or not local
        or origin not in allowed
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise ApplicationError("source_policy_forbidden", "Local settings access denied", 403)
    if (
        not expected
        or len(supplied) > 256
        or not secrets.compare_digest(supplied.encode(), expected.encode())
    ):
        logger.warning(
            "Local settings authentication rejected",
            extra={"event_data": {"actor": "unauthenticated"}},
        )
        raise ApplicationError("admin_auth_required", "Management token required", 401)


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: PolicyMode
    revision: int = Field(ge=0, strict=True)


@router.get("/source-policy", response_model=SourcePolicy)
def read_policy(policy_service: Annotated[SourcePolicyService, Depends(service)]):
    return policy_service.read()


@router.put("/source-policy", response_model=SourcePolicy, dependencies=[Depends(authenticate)])
def save_policy(
    body: PolicyUpdate, policy_service: Annotated[SourcePolicyService, Depends(service)]
):
    return policy_service.save(body.mode, body.revision)
