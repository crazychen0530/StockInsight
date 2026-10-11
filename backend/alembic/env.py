"""Alembic runtime environment without import-time database access."""

import os
from logging.config import fileConfig

from alembic import context
from app import models  # noqa: F401  # Register all model tables with Base.metadata.
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Read the migration URL only when an Alembic command needs it."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        message = "DATABASE_URL is required to execute database migrations"
        raise RuntimeError(message)
    return database_url


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a short-lived SQLAlchemy Engine."""
    from app.core.database import create_database_engine

    engine = create_database_engine(get_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
