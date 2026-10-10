"""Contract tests for the API liveness endpoint."""

import json

import pytest
from httpx2 import ASGITransport, AsyncClient, Response

from app import __version__
from app.main import app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    """Use the asyncio backend available in the application runtime."""
    return "asyncio"


async def request_health() -> Response:
    """Send an HTTP request directly through the ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/api/v1/health")


async def test_health_returns_http_200() -> None:
    response = await request_health()

    assert response.status_code == 200


async def test_health_response_structure() -> None:
    response = await request_health()

    assert set(response.json()) == {"status", "version"}


async def test_health_reports_application_version_and_status() -> None:
    response = await request_health()

    assert response.json() == {"status": "ok", "version": __version__}


async def test_health_does_not_expose_sensitive_configuration() -> None:
    response = await request_health()
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
