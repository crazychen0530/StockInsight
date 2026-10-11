"""Shared isolated application/client and explicitly disposable database fixtures."""

import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url

from app.core.config import Settings, load_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Never fall back to a developer DATABASE_URL; libpq variables may authenticate
    # the explicitly named disposable TEST_DATABASE_URL on the same server.
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return load_settings({"APP_ENV": "test"})


@pytest.fixture
def application(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(application: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=application)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", trust_env=False
    ) as value:
        yield value


@pytest.fixture
def migration_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL migration tests")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith(
        "_migration_test"
    ):
        pytest.fail("Use postgresql+psycopg and a disposable database ending in _migration_test")
    return value
