"""FastAPI application entry point."""

from fastapi import FastAPI

from app import __version__
from app.api.router import api_router


def create_app() -> FastAPI:
    """Create and configure the StockInsight API application."""
    application = FastAPI(
        title="StockInsight API",
        version=__version__,
        description="A-share research API. Trading operations are not supported.",
    )
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
