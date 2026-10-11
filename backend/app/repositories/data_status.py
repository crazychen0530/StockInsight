"""Bounded local synchronization status reads."""

from sqlalchemy import select

from app.models import DataSyncJob
from app.repositories.sync_jobs import _view


class DataStatusRepository:
    def __init__(self, session):
        self.session = session

    def recent(self, limit):
        return [
            {**_view(row).__dict__, "started_at": row.started_at, "finished_at": row.finished_at}
            for row in self.session.scalars(
                select(DataSyncJob)
                .order_by(DataSyncJob.started_at.desc(), DataSyncJob.id)
                .limit(limit)
            )
        ]
