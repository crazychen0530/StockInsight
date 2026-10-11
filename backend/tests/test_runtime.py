"""Real ASGI behavior for errors, correlation, concurrency and safe diagnostic logs."""

import asyncio
import io
import json
import logging
import re
import sys

import pytest
from fastapi import FastAPI, HTTPException
from httpx2 import AsyncClient
from pydantic import BaseModel, Field

from app.core.errors import ApplicationError
from app.core.logging import JsonFormatter, Redactor, SafeStdoutHandler, request_id_context
from app.schemas.error import ErrorResponse

pytestmark = pytest.mark.anyio


class FixturePayload(BaseModel):
    quantity: int = Field(gt=0)


@pytest.fixture
def error_routes(application: FastAPI) -> None:
    @application.post("/fixture/validation")
    async def validate(payload: FixturePayload) -> dict[str, int]:
        return {"quantity": payload.quantity}

    @application.get("/fixture/http")
    async def http_failure() -> None:
        raise HTTPException(503, detail="token=fixture-http-private", headers={"Retry-After": "5"})

    @application.get("/fixture/application")
    async def application_failure() -> None:
        raise ApplicationError("fixture_unavailable", "Fixture data unavailable", 409)

    @application.get("/fixture/crash/{item}")
    async def crash(item: str) -> None:
        raise RuntimeError("postgresql+psycopg://fixture:fixture-crash-secret@db/production")

    @application.get("/fixture/concurrent")
    async def concurrent() -> dict[str, str | None]:
        before = request_id_context.get()
        await asyncio.sleep(0)
        assert request_id_context.get() == before
        return {"request_id": before}


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status
    body = response.json()
    ErrorResponse.model_validate(body)
    assert body["code"] == code
    assert body["request_id"] == response.headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", body["request_id"])
    return body


async def test_request_id_is_generated_not_echoed(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/health", headers={"X-Request-ID": "token=private-caller-id"}
    )
    assert response.json() == {"status": "ok", "version": "0.1.0"}
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
    assert request_id_context.get() is None


async def test_not_found_and_method_error_contract(client: AsyncClient) -> None:
    assert_error(await client.get("/missing"), 404, "not_found")
    response = await client.post("/api/v1/health")
    assert_error(response, 405, "method_not_allowed")
    assert response.headers["allow"] == "GET"


async def test_http_and_application_error_contract(error_routes, client: AsyncClient) -> None:
    response = await client.get("/fixture/http")
    body = assert_error(response, 503, "service_unavailable")
    assert body["message"] == "Service Unavailable"
    assert "fixture-http-private" not in response.text
    assert response.headers["retry-after"] == "5"
    response = await client.get("/fixture/application")
    body = assert_error(response, 409, "fixture_unavailable")
    assert body["message"] == "Fixture data unavailable"


@pytest.mark.parametrize("body", [{"quantity": "fixture-validation-secret"}, {"quantity": -1}, {}])
async def test_validation_omits_input_and_context(
    error_routes, client: AsyncClient, body: dict
) -> None:
    response = await client.post("/fixture/validation", json=body)
    payload = assert_error(response, 422, "validation_error")
    assert payload["details"]
    assert all(set(item) == {"location", "type"} for item in payload["details"])
    assert "fixture-validation-secret" not in response.text


async def test_malformed_json_is_a_safe_validation_error(error_routes, client: AsyncClient) -> None:
    response = await client.post(
        "/fixture/validation",
        content=b'{"quantity":"private',
        headers={"Content-Type": "application/json"},
    )
    assert_error(response, 422, "validation_error")
    assert "private" not in response.text


async def test_crash_is_logged_without_internal_text_or_request_secrets(
    capsys: pytest.CaptureFixture,
    error_routes,
    client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = await client.get(
        "/fixture/crash/fixture-path-secret?token=fixture-query-secret",
        headers={"Authorization": "Bearer fixture-header-secret"},
    )
    assert_error(response, 500, "internal_error")
    captured = capsys.readouterr()
    serialized = captured.out + captured.err + response.text + caplog.text
    for secret in (
        "fixture-crash-secret",
        "fixture-path-secret",
        "fixture-query-secret",
        "fixture-header-secret",
        "postgresql+psycopg://",
    ):
        assert secret not in serialized
    logs = [json.loads(line) for line in captured.out.splitlines()]
    failure = next(entry for entry in logs if entry["message"] == "request_failed")
    assert failure["context"]["exception"]["type"] == "RuntimeError"
    assert failure["context"]["exception"]["origin"]["function"] == "crash"
    assert "frames" not in failure["context"]["exception"]
    assert all(entry["request_id"] == response.headers["x-request-id"] for entry in logs)
    completion = next(entry for entry in logs if entry["message"] == "request_completed")
    assert completion["context"]["route"] == "/fixture/crash/{item}"


async def test_concurrent_requests_keep_distinct_context(error_routes, client: AsyncClient) -> None:
    responses = await asyncio.gather(*(client.get("/fixture/concurrent") for _ in range(12)))
    ids = [response.headers["x-request-id"] for response in responses]
    assert len(set(ids)) == 12
    assert [response.json()["request_id"] for response in responses] == ids
    assert request_id_context.get() is None


async def test_test_only_routes_are_not_in_production_app(client: AsyncClient) -> None:
    document = (await client.get("/openapi.json")).json()
    assert set(document["paths"]) == {"/api/v1/health"}
    assert "ErrorResponse" in document["components"]["schemas"]


async def test_formatter_redacts_nested_credentials_and_connection_strings() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(Redactor(("fixture-known-secret",))))
    logger = logging.Logger("fixture")
    logger.addHandler(handler)
    logger.info(
        "password=unknown-secret Bearer credential fixture-known-secret postgresql://u:p@db/x",
        extra={
            "event_data": {
                "nested": {"Authorization": "anything", "api_key": "anything", "count": 3}
            }
        },
    )
    output = stream.getvalue()
    for secret in ("unknown-secret", "credential", "fixture-known-secret", "u:p@db", "anything"):
        assert secret not in output
    assert json.loads(output)["context"]["nested"]["count"] == 3


async def test_failed_log_sink_does_not_dump_sensitive_record(monkeypatch, capsys) -> None:
    class BrokenStream:
        def write(self, value: str) -> None:
            raise OSError("fixture-sink-private")

        def flush(self) -> None:
            pass

    handler = SafeStdoutHandler()
    handler.setFormatter(JsonFormatter(Redactor()))
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", BrokenStream())
        handler.handle(logging.makeLogRecord({"msg": "fixture-record-private"}))
    captured = capsys.readouterr()
    assert captured.err == "StockInsight logging sink unavailable\n"
    assert captured.out == ""
