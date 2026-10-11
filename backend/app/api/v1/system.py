"""Read-only local synchronization status routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.schemas.data_status import DataStatusResponse
from app.services.data_status import DataStatusService

router = APIRouter(prefix="/system", tags=["system"])


def get_data_status_service(request: Request):
    return DataStatusService(request.app.state.query_database.session)


@router.get("/data-status", response_model=DataStatusResponse)
def data_status(
    service: Annotated[DataStatusService, Depends(get_data_status_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return service.recent(limit)
