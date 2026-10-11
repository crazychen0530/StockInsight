"""Indicator input reads, versioned idempotent writes and bounded joined queries."""

from dataclasses import asdict
from datetime import UTC, date, datetime

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.analysis.moving_averages import ClosePoint
from app.models import DailyPrice, TechnicalIndicator


class IndicatorRepository:
    def __init__(self, session: Session):
        self.session = session

    def closes(self, symbol: str):
        rows = self.session.execute(
            select(DailyPrice.symbol, DailyPrice.trade_date, DailyPrice.close)
            .where(DailyPrice.symbol == symbol)
            .order_by(DailyPrice.trade_date)
        )
        return tuple(ClosePoint(*row) for row in rows)

    def upsert(self, rows):
        table = TechnicalIndicator.__table__
        changed = 0
        now = datetime.now(UTC)
        for offset in range(0, len(rows), 500):
            statement = insert(table).values(
                [{**asdict(row), "computed_at": now} for row in rows[offset : offset + 500]]
            )
            incoming = statement.excluded
            fields = ("ma5", "ma20", "ma60")
            statement = statement.on_conflict_do_update(
                index_elements=[table.c.symbol, table.c.trade_date, table.c.calculation_version],
                set_={key: incoming[key] for key in (*fields, "computed_at")},
                where=or_(*(table.c[key].is_distinct_from(incoming[key]) for key in fields)),
            )
            changed += len(self.session.scalars(statement.returning(table.c.trade_date)).all())
        return changed

    def query(self, symbol: str, start: date, end: date, version: str, limit: int):
        return (
            self.session.execute(
                select(
                    TechnicalIndicator.symbol,
                    TechnicalIndicator.trade_date,
                    TechnicalIndicator.calculation_version,
                    TechnicalIndicator.ma5,
                    TechnicalIndicator.ma20,
                    TechnicalIndicator.ma60,
                    TechnicalIndicator.computed_at,
                    DailyPrice.source,
                    DailyPrice.fetched_at,
                    DailyPrice.adjustment,
                )
                .join(
                    DailyPrice,
                    (DailyPrice.symbol == TechnicalIndicator.symbol)
                    & (DailyPrice.trade_date == TechnicalIndicator.trade_date),
                )
                .where(
                    TechnicalIndicator.symbol == symbol,
                    TechnicalIndicator.trade_date.between(start, end),
                    TechnicalIndicator.calculation_version == version,
                )
                .order_by(TechnicalIndicator.trade_date)
                .limit(limit)
            )
            .mappings()
            .all()
        )
