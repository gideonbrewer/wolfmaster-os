"""SQLAlchemy 2.x ORM mapping for canonical trades and import batches."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ImportBatchRow(Base):
    """One import attempt of one source file (audit trail + file-level dedup)."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rows_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_import_batches_file_sha256", "file_sha256"),)


class TradeRow(Base):
    """Canonical trade storage. `fingerprint` is globally unique — the
    database, not application code, is the final duplicate gate."""

    __tablename__ = "trades"

    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    import_batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )

    strategy_family: Mapped[str | None] = mapped_column(String(128))
    strategy_name: Mapped[str | None] = mapped_column(String(256))
    strategy_version: Mapped[str | None] = mapped_column(String(64))
    bot_name: Mapped[str | None] = mapped_column(String(256), index=True)
    environment: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")

    asset_class: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    instrument_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    underlying_symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    contract_description: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    opened_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=False), index=True)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=False))
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=False))
    dte_at_entry: Mapped[int | None] = mapped_column(Integer)
    days_in_trade: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    premium: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    risk: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    return_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    return_on_risk: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    mfe_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    mae_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    mfe_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=False))
    mae_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=False))

    underlying_entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    underlying_exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))

    timeframe: Mapped[str | None] = mapped_column(String(32))
    target_delta: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    dte_setting: Mapped[int | None] = mapped_column(Integer)
    contract_count_setting: Mapped[int | None] = mapped_column(Integer)
    parse_sources: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_trades_bot_opened", "bot_name", "opened_at"),
        Index("ix_trades_strategy_family", "strategy_family"),
    )
