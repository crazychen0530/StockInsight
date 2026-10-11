"""PostgreSQL daily-price UPSERT; the caller validates and owns the transaction."""

from dataclasses import asdict

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.collectors.provider import DailyBar, MarketDataBatch
from app.models import DailyPrice


class DailyPriceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, batch: MarketDataBatch[DailyBar]) -> int:
        """Count inserted/changed rows; identical values preserve their original receipt time."""
        table = DailyPrice.__table__
        changed = 0
        for offset in range(0, len(batch.records), 500):
            statement = insert(table).values(
                [
                    {
                        **asdict(row),
                        "source": batch.source,
                        "adjustment": batch.adjustment,
                        "fetched_at": batch.fetched_at,
                    }
                    for row in batch.records[offset : offset + 500]
                ]
            )
            incoming = statement.excluded
            fields = (
                "open",
                "high",
                "low",
                "close",
                "volume_shares",
                "amount_cny",
                "source",
                "adjustment",
            )
            statement = statement.on_conflict_do_update(
                index_elements=[table.c.symbol, table.c.trade_date],
                set_={field: incoming[field] for field in (*fields, "fetched_at")},
                where=or_(*(table.c[field].is_distinct_from(incoming[field]) for field in fields)),
            )
            changed += len(self.session.scalars(statement.returning(table.c.trade_date)).all())
        return changed
