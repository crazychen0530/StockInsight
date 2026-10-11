"""PostgreSQL stock identity persistence; accepts already validated internal DTOs."""

from dataclasses import asdict

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.collectors.provider import StockInfo
from app.models import Stock


class StockRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def exists(self, symbol: str) -> bool:
        return self.session.scalar(select(Stock.symbol).where(Stock.symbol == symbol)) is not None

    def upsert(self, records: tuple[StockInfo, ...]) -> int:
        """Return changed rows (inserted or updated), not the number of new securities."""
        changed = 0
        table = Stock.__table__
        for offset in range(0, len(records), 500):
            statement = insert(table).values(
                [asdict(row) for row in records[offset : offset + 500]]
            )
            incoming = statement.excluded
            updates = {
                "name": incoming.name,
                "exchange": incoming.exchange,
                "list_date": func.coalesce(incoming.list_date, table.c.list_date),
                "status": case(
                    (incoming.status == "unknown", table.c.status), else_=incoming.status
                ),
            }
            statement = statement.on_conflict_do_update(
                index_elements=[table.c.symbol],
                set_=updates,
                where=or_(
                    *(table.c[field].is_distinct_from(value) for field, value in updates.items())
                ),
            )
            # psycopg can report rowcount=-1; RETURNING counts actual inserted/updated rows.
            changed += len(self.session.scalars(statement.returning(table.c.symbol)).all())
        return changed

    def search(self, query: str, page: int, page_size: int) -> tuple[tuple[StockInfo, ...], int]:
        conditions = []
        if query:
            conditions.append(
                or_(
                    Stock.symbol.icontains(query, autoescape=True),
                    Stock.name.icontains(query, autoescape=True),
                )
            )
        total = self.session.scalar(select(func.count()).select_from(Stock).where(*conditions))
        rows = self.session.scalars(
            select(Stock)
            .where(*conditions)
            .order_by(Stock.symbol)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return tuple(
            StockInfo(row.symbol, row.name, row.exchange, row.list_date, row.status) for row in rows
        ), total
