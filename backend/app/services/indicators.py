"""Analysis service keeps computation outside the HTTP request path."""

from app.analysis.moving_averages import calculate_moving_averages
from app.repositories.indicators import IndicatorRepository


class IndicatorService:
    @staticmethod
    def recalculate(session, symbol):
        repository = IndicatorRepository(session)
        return repository.upsert(calculate_moving_averages(repository.closes(symbol)))
