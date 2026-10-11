"""Analysis service keeps computation outside the HTTP request path."""

from app.analysis.moving_averages import calculate_moving_averages
from app.collectors.validator import normalize_symbol
from app.core.errors import ApplicationError
from app.repositories.indicators import IndicatorRepository


class IndicatorService:
    @staticmethod
    def recalculate(session, symbol):
        repository = IndicatorRepository(session)
        return repository.upsert(calculate_moving_averages(repository.closes(symbol)))

    @staticmethod
    def rebuild(session_factory, symbol):
        symbol = normalize_symbol(symbol)
        with session_factory() as session, session.begin():
            repository = IndicatorRepository(session)
            if not repository.lock_stock(symbol):
                raise ApplicationError("stock_not_found", "Stock not found in local database", 404)
            return IndicatorService.recalculate(session, symbol)
