"""SQLAlchemy 2 base types and lazy database session construction."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings, load_settings


class Base(DeclarativeBase):
    """Declarative base for Alembic-managed persistence models."""


def create_database_engine(database_url: str) -> Engine:
    """Create an engine without opening a database connection eagerly."""
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the configured SQLAlchemy 2 session factory."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_configured_database_engine(settings: Settings | None = None) -> Engine:
    """Use the selected environment without opening a connection or creating tables."""
    configuration = settings if settings is not None else load_settings()
    return create_database_engine(configuration.database_url_value())


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session and always close it after the caller finishes."""
    with session_factory() as session:
        yield session
