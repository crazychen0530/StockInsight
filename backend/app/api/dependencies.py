"""Lazy database ownership per application; health never resolves database settings."""

import logging
from threading import Lock

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import ConfigurationError, Settings
from app.core.database import create_configured_database_engine, create_session_factory
from app.core.errors import ApplicationError
from app.services.stock_queries import StockQueryService

logger = logging.getLogger("stockinsight.api.database")


class QueryDatabase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: Engine | None = None
        self.factory: sessionmaker[Session] | None = None
        self.lock = Lock()

    def session(self) -> Session:
        with self.lock:
            if self.factory is None:
                try:
                    self.engine = create_configured_database_engine(self.settings)
                    self.factory = create_session_factory(
                        self.engine.execution_options(postgresql_readonly=True)
                    )
                except ConfigurationError:
                    logger.error("Stock query database configuration unavailable")
                    raise ApplicationError(
                        "stock_query_unavailable", "Stock query storage unavailable", 503
                    ) from None
            factory = self.factory
        return factory()

    def close(self) -> None:
        with self.lock:
            if self.engine is not None:
                self.engine.dispose()
                self.engine = None
                self.factory = None


def get_stock_query_service(request: Request) -> StockQueryService:
    return StockQueryService(request.app.state.query_database.session)
