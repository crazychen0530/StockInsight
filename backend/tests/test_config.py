"""Environment separation, configuration validation and credential-safe failures."""

import pytest
from sqlalchemy.engine import make_url

from app.core.config import ConfigurationError, load_settings
from app.core.database import create_configured_database_engine


def test_defaults_do_not_load_local_dotenv_or_connect() -> None:
    settings = load_settings({})
    assert settings.app_env == "development"
    assert settings.database_url is None
    with pytest.raises(ConfigurationError, match="Database requires"):
        create_configured_database_engine(settings)


def test_compose_password_free_url_and_libpq_compatibility() -> None:
    settings = load_settings(
        {
            "DATABASE_URL": "postgresql+psycopg:///stockinsight",
            "PGHOST": "db",
            "PGUSER": "stockinsight",
            "PGPASSWORD": "fixture-private-password",
        }
    )
    assert settings.database_url_value() == "postgresql+psycopg:///stockinsight"
    assert "fixture-private-password" not in repr(settings)
    engine = create_configured_database_engine(settings)
    assert engine.url.database == "stockinsight"
    engine.dispose()


def test_pg_fields_build_url_with_special_password_without_connecting() -> None:
    settings = load_settings(
        {
            "PGHOST": "db",
            "PGPORT": "55432",
            "PGUSER": "fixture",
            "PGDATABASE": "fixture_dev",
            "PGPASSWORD": "p@ss:/?#word",
        }
    )
    url = make_url(settings.database_url_value())
    assert (url.host, url.port, url.database, url.password) == (
        "db",
        55432,
        "fixture_dev",
        "p@ss:/?#word",
    )


def test_test_environment_never_falls_back_to_developer_database() -> None:
    settings = load_settings({"APP_ENV": "test", "DATABASE_URL": "postgresql+psycopg:///developer"})
    with pytest.raises(ConfigurationError, match="TEST_DATABASE_URL"):
        settings.database_url_value()


@pytest.mark.parametrize("name", ["stockinsight", "production", "test"])
def test_test_database_requires_explicit_test_suffix(name: str) -> None:
    settings = load_settings(
        {"APP_ENV": "test", "TEST_DATABASE_URL": f"postgresql+psycopg:///{name}"}
    )
    with pytest.raises(ConfigurationError, match="end in _test"):
        settings.database_url_value()


def test_test_database_wins_and_config_has_no_cross_app_cache() -> None:
    settings = load_settings(
        {
            "APP_ENV": "test",
            "DATABASE_URL": "postgresql+psycopg:///developer",
            "TEST_DATABASE_URL": "postgresql+psycopg:///fixture_migration_test",
        }
    )
    assert settings.database_url_value().endswith("/fixture_migration_test")
    assert load_settings({"LOG_LEVEL": "ERROR"}).log_level == "ERROR"
    assert load_settings({}).log_level == "INFO"


@pytest.mark.parametrize(
    "environment",
    [
        {"APP_ENV": "invalid-secret"},
        {"LOG_LEVEL": "invalid-secret"},
        {"PGPORT": "0"},
        {"PGPORT": "65536"},
        {"APP_TIMEZONE": "invalid-secret"},
        {"DATABASE_URL": "postgresql://fixture:invalid-secret@db/example"},
        {"DATABASE_URL": "invalid-secret"},
        {"DATABASE_URL": "postgresql+psycopg://db:65536/fixture"},
        {"TEST_DATABASE_URL": "postgresql+psycopg:///fixture_test?dbname=production"},
    ],
)
def test_invalid_configuration_is_sanitized(environment: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError) as error:
        load_settings(environment)
    assert "invalid-secret" not in str(error.value)
