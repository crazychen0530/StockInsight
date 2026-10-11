"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.dependencies import QueryDatabase
from app.api.router import api_router
from app.core.config import Settings, load_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.schemas.error import ErrorResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the StockInsight API application."""
    configuration = settings if settings is not None else load_settings()
    database = QueryDatabase(configuration)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            database.close()

    application = FastAPI(
        title="StockInsight API",
        version=__version__,
        description="A-share research API. Trading operations are not supported.",
        lifespan=lifespan,
        responses={status: {"model": ErrorResponse} for status in (400, 404, 405, 422, 500, 503)},
    )
    application.state.settings = configuration
    application.state.query_database = database
    application.state.redactor = configure_logging(configuration)
    register_error_handlers(application)
    application.add_middleware(RequestContextMiddleware)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
