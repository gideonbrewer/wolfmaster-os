"""Shared enumerations for the canonical trade model.

Designed so the same model can later carry stocks, options, crypto, and
futures without schema changes.
"""

from __future__ import annotations

import enum


class TradeSource(enum.StrEnum):
    """Where a trade record was imported from."""

    OPTION_ALPHA = "option_alpha"
    MANUAL = "manual"


class AssetClass(enum.StrEnum):
    EQUITY = "equity"
    EQUITY_OPTION = "equity_option"
    CRYPTO = "crypto"
    FUTURE = "future"
    UNKNOWN = "unknown"


class InstrumentType(enum.StrEnum):
    """Concrete instrument / structure type."""

    STOCK = "stock"
    SINGLE_OPTION = "single_option"
    VERTICAL_SPREAD = "vertical_spread"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURES_CONTRACT = "futures_contract"
    OTHER = "other"
    UNKNOWN = "unknown"


class Direction(enum.StrEnum):
    """Net directional bias of the position (not order side).

    CREDIT/DEBIT capture option structures where long/short is ambiguous
    at the position level.
    """

    LONG = "long"
    SHORT = "short"
    CREDIT = "credit"
    DEBIT = "debit"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class TradeStatus(enum.StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


class TradeEnvironment(enum.StrEnum):
    """Live vs paper, when identifiable from the source."""

    LIVE = "live"
    PAPER = "paper"
    UNKNOWN = "unknown"


class ParseSource(enum.StrEnum):
    """Provenance of a derived field value (never invent values)."""

    SOURCE_COLUMN = "source_column"  # taken directly from an export column
    BOT_NAME = "bot_name"  # parsed from the bot name
    DESCRIPTION = "description"  # parsed from the contract description
    TAGS = "tags"  # parsed from tags
    DERIVED = "derived"  # computed from other trusted fields
