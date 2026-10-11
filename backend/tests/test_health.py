"""Contract tests for the API liveness endpoint."""

import json

import pytest
from httpx2 import AsyncClient

from app import __version__

pytestmark = pytest.mark.anyio


async def test_health_returns_http_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200


async def test_health_response_structure(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert set(response.json()) == {"status", "version"}


async def test_health_reports_application_version_and_status(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.json() == {"status": "ok", "version": __version__}


async def test_health_does_not_expose_sensitive_configuration(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    serialized_payload = json.dumps(response.json()).lower()
    forbidden_terms = {
        "connection",
        "database",
        "password",
        "postgresql",
        "secret",
        "token",
    }

    assert all(term not in serialized_payload for term in forbidden_terms)
