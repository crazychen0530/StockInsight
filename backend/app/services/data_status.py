"""Read-only task status application service."""

from dataclasses import asdict

from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import ApplicationError
from app.repositories.data_status import DataStatusRepository
from app.schemas.data_status import DataStatusResponse
from app.services.stock_queries import _unavailable


class DataStatusService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def recent(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ApplicationError("invalid_job_limit", "Invalid job list limit", 422)
        try:
            with self.session_factory() as session, session.begin():
                rows = DataStatusRepository(session).recent(limit)
                return DataStatusResponse(
                    items=[{**row, "scope": asdict(row["scope"])} for row in rows], limit=limit
                )
        except SQLAlchemyError:
            raise _unavailable() from None
