"""SQLAlchemy 2 base types and lazy database session construction."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for future Alembic-managed models."""


def create_database_engine(database_url: str) -> Engine:
    """Create an engine without opening a database connection eagerly."""
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the configured SQLAlchemy 2 session factory."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session and always close it after the caller finishes."""
    with session_factory() as session:
        yield session
