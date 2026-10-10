"""API process liveness endpoint."""

from fastapi import APIRouter

from app import __version__
from app.schemas.health import HealthResponse

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API process liveness",
)
async def get_health() -> HealthResponse:
    """Report only that the API process can serve requests."""
    return HealthResponse(status="ok", version=__version__)
