"""Canonical trade model (Pydantic v2).

This is the single internal representation every import source must map
into. Monetary values use Decimal; percentages are stored as percent
units (e.g. 12.5 == +12.5%). Fields that cannot be confidently parsed
from a source are left as None — values are never invented — and the
provenance of derived fields is recorded in `parse_sources`.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from wolf_trading_os.domain.enums import (
    AssetClass,
    Direction,
    InstrumentType,
    ParseSource,
    TradeEnvironment,
    TradeSource,
    TradeStatus,
)


class StrategyAttributes(BaseModel):
    """Strategy metadata parsed from bot name / description / tags.

    Every populated field must have an entry in `parse_sources` naming
    where the value came from. Unparseable values stay None.
    """

    model_config = ConfigDict(frozen=True)

    strategy_family: str | None = None  # e.g. "Hulk"
    strategy_name: str | None = None
    strategy_version: str | None = None
    timeframe: str | None = None  # e.g. "0DTE", "intraday", "multi-day"
    target_delta: Decimal | None = None  # e.g. 0.50
    dte_setting: int | None = None  # configured DTE, e.g. 0, 1, 2
    contract_count_setting: int | None = None
    environment: TradeEnvironment = TradeEnvironment.UNKNOWN
    parse_sources: dict[str, ParseSource] = Field(default_factory=dict)


class CanonicalTrade(BaseModel):
    """A single completed (or open) trade, normalized across sources."""

    model_config = ConfigDict(frozen=True)

    # Identity
    trade_id: UUID = Field(default_factory=uuid4)
    fingerprint: str  # deterministic hash of identifying source fields
    fingerprint_version: str = "oa2"  # algorithm version (see fingerprint.py)
    source: TradeSource

    # Strategy / provenance
    strategy_family: str | None = None
    strategy_name: str | None = None
    strategy_version: str | None = None
    bot_name: str | None = None
    environment: TradeEnvironment = TradeEnvironment.UNKNOWN

    # Instrument
    asset_class: AssetClass = AssetClass.UNKNOWN
    instrument_type: InstrumentType = InstrumentType.UNKNOWN
    underlying_symbol: str
    contract_description: str | None = None
    direction: Direction = Direction.UNKNOWN
    status: TradeStatus = TradeStatus.UNKNOWN

    # Size & timing
    quantity: Decimal | None = None
    opened_at: dt.datetime | None = None
    closed_at: dt.datetime | None = None
    expires_at: dt.datetime | None = None
    dte_at_entry: int | None = None
    days_in_trade: Decimal | None = None

    # Prices & money
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    premium: Decimal | None = None  # premium received/paid or capital deployed
    risk: Decimal | None = None  # max defined risk (capital at risk)
    realized_pnl: Decimal | None = None
    return_pct: Decimal | None = None  # percent units
    return_on_risk: Decimal | None = None  # percent units

    # Excursions (percent units, relative to the same base as return_pct)
    mfe_pct: Decimal | None = None
    mae_pct: Decimal | None = None
    mfe_at: dt.datetime | None = None
    mae_at: dt.datetime | None = None

    # Underlying context
    underlying_entry_price: Decimal | None = None
    underlying_exit_price: Decimal | None = None

    # Strategy settings parsed from bot name / description
    timeframe: str | None = None
    target_delta: Decimal | None = None
    dte_setting: int | None = None
    contract_count_setting: int | None = None
    parse_sources: dict[str, ParseSource] = Field(default_factory=dict)

    # Misc
    tags: tuple[str, ...] = ()
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None
