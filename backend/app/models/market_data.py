"""Core stock, daily price, and technical indicator persistence models."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Stock(Base):
    """Canonical A-share identity and listing state."""

    __tablename__ = "stocks"
    __table_args__ = (
        CheckConstraint("symbol ~ '^[0-9]{6}\\.(SH|SZ)$'", name="ck_stocks_symbol_format"),
        CheckConstraint("exchange IN ('SH', 'SZ')", name="ck_stocks_exchange"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_stocks_name_not_blank"),
        CheckConstraint("length(btrim(status)) > 0", name="ck_stocks_status_not_blank"),
        Index("ix_stocks_name", "name"),
        Index("ix_stocks_exchange_status", "exchange", "status"),
    )

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)


class DailyPrice(Base):
    """Unadjusted daily OHLCV data in CNY, shares, and CNY amount units."""

    __tablename__ = "daily_prices"
    __table_args__ = (
        PrimaryKeyConstraint("symbol", "trade_date", name="pk_daily_prices"),
        CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0",
            name="ck_daily_prices_nonnegative_ohlc",
        ),
        CheckConstraint(
            "high >= open AND high >= close AND high >= low AND low <= open AND low <= close",
            name="ck_daily_prices_ohlc_relationship",
        ),
        CheckConstraint("volume_shares >= 0", name="ck_daily_prices_volume_nonnegative"),
        CheckConstraint("amount_cny >= 0", name="ck_daily_prices_amount_nonnegative"),
        CheckConstraint("adjustment = 'none'", name="ck_daily_prices_adjustment_none"),
        CheckConstraint("length(btrim(source)) > 0", name="ck_daily_prices_source_not_blank"),
        Index("ix_daily_prices_trade_date", "trade_date"),
    )

    symbol: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("stocks.symbol", name="fk_daily_prices_symbol_stocks"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume_shares: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    adjustment: Mapped[str] = mapped_column(String(16), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TechnicalIndicator(Base):
    """Versioned moving averages; values are null until enough history exists."""

    __tablename__ = "technical_indicators"
    __table_args__ = (
        PrimaryKeyConstraint(
            "symbol",
            "trade_date",
            "calculation_version",
            name="pk_technical_indicators",
        ),
        CheckConstraint(
            "ma5 IS NULL OR ma5 >= 0",
            name="ck_technical_indicators_ma5_nonnegative",
        ),
        CheckConstraint(
            "ma20 IS NULL OR ma20 >= 0",
            name="ck_technical_indicators_ma20_nonnegative",
        ),
        CheckConstraint(
            "ma60 IS NULL OR ma60 >= 0",
            name="ck_technical_indicators_ma60_nonnegative",
        ),
        CheckConstraint(
            "length(btrim(calculation_version)) > 0",
            name="ck_technical_indicators_version_not_blank",
        ),
        Index("ix_technical_indicators_symbol_trade_date", "symbol", "trade_date"),
    )

    symbol: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("stocks.symbol", name="fk_technical_indicators_symbol_stocks"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), nullable=False)
    ma5: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    ma20: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    ma60: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
