"""Explicit environment configuration; never implicitly load a developer .env."""

import os
from collections.abc import Mapping
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError, field_validator
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


class ConfigurationError(RuntimeError):
    """A configuration failure whose message is safe to display."""


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    app_timezone: str = "Asia/Shanghai"
    market_data_timeout_seconds: float = 30.0
    market_data_daily_interface: Literal["stock_zh_a_hist", "stock_zh_a_hist_tx"] = (
        "stock_zh_a_hist"
    )
    source_policy_directory: str | None = None
    local_admin_token: SecretStr | None = None
    database_url: SecretStr | None = None
    test_database_url: SecretStr | None = None
    pg_host: str | None = None
    pg_port: int = 5432
    pg_database: str | None = None
    pg_user: str | None = None
    pg_password: SecretStr | None = None

    @field_validator("market_data_timeout_seconds")
    @classmethod
    def validate_provider_timeout(cls, value: float) -> float:
        if not 0 < value <= 300:
            raise ValueError("Invalid market data timeout")
        return value

    @field_validator("local_admin_token")
    @classmethod
    def validate_admin_token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value():
            return None
        if value is not None and not 32 <= len(value.get_secret_value()) <= 256:
            raise ValueError("Management token must have at least 32 characters")
        return value

    @field_validator("pg_port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("Invalid database port")
        return value

    @field_validator("app_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Invalid application timezone") from None
        return value

    @field_validator("database_url", "test_database_url")
    @classmethod
    def validate_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            try:
                url = make_url(value.get_secret_value())
                if url.drivername != "postgresql+psycopg" or not url.database:
                    raise ValueError
                if url.port is not None and not 1 <= url.port <= 65535:
                    raise ValueError
                if {"dbname", "database"}.intersection(url.query):
                    raise ValueError
            except (ArgumentError, ValueError, TypeError):
                raise ValueError("Invalid PostgreSQL URL") from None
        return value

    def database_url_value(self) -> str:
        """Resolve a URL only for an explicit database operation, never for health."""
        if self.app_env == "test":
            if self.test_database_url is None:
                raise ConfigurationError("Test database requires TEST_DATABASE_URL")
            value = self.test_database_url.get_secret_value()
            if not (make_url(value).database or "").endswith("_test"):
                raise ConfigurationError("Test database name must end in _test")
            return value
        if self.database_url is not None:
            return self.database_url.get_secret_value()
        if self.pg_host and self.pg_user and self.pg_database:
            return URL.create(
                "postgresql+psycopg",
                username=self.pg_user,
                password=self.pg_password.get_secret_value() if self.pg_password else None,
                host=self.pg_host,
                port=self.pg_port,
                database=self.pg_database,
            ).render_as_string(hide_password=False)
        raise ConfigurationError("Database requires DATABASE_URL or PGHOST/PGUSER/PGDATABASE")

    def secret_values(self) -> tuple[str, ...]:
        values = []
        for value in (
            self.database_url,
            self.test_database_url,
            self.pg_password,
            self.local_admin_token,
        ):
            if value is not None:
                raw = value.get_secret_value()
                values.append(raw)
                if "://" in raw:
                    password = make_url(raw).password
                    if password:
                        values.append(password)
        return tuple(value for value in values if value)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read a whitelist of environment values without global settings caching."""
    environment = os.environ if environ is None else environ
    names = {
        "APP_ENV": "app_env",
        "LOG_LEVEL": "log_level",
        "APP_TIMEZONE": "app_timezone",
        "MARKET_DATA_TIMEOUT_SECONDS": "market_data_timeout_seconds",
        "MARKET_DATA_DAILY_INTERFACE": "market_data_daily_interface",
        "SOURCE_POLICY_DIRECTORY": "source_policy_directory",
        "LOCAL_ADMIN_TOKEN": "local_admin_token",
        "DATABASE_URL": "database_url",
        "TEST_DATABASE_URL": "test_database_url",
        "PGHOST": "pg_host",
        "PGPORT": "pg_port",
        "PGDATABASE": "pg_database",
        "PGUSER": "pg_user",
        "PGPASSWORD": "pg_password",
    }
    try:
        return Settings.model_validate(
            {field: environment[name] for name, field in names.items() if name in environment}
        )
    except (ValidationError, ValueError):
        raise ConfigurationError(
            "Invalid application configuration; check environment values"
        ) from None
