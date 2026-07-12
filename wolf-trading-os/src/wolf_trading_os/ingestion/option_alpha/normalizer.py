"""Normalize one raw Option Alpha CSV row into a CanonicalTrade.

Fail-closed philosophy: rows missing identity-critical values (symbol,
open date, quantity, P&L for closed trades) are rejected with explicit
reasons. Optional fields that fail to parse produce warnings and become
None — they never abort the row, and values are never guessed.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from wolf_trading_os.domain import (
    AssetClass,
    CanonicalTrade,
    Direction,
    InstrumentType,
    ParseSource,
    TradeEnvironment,
    TradeSource,
    TradeStatus,
)
from wolf_trading_os.ingestion.option_alpha import values
from wolf_trading_os.ingestion.option_alpha.bot_parser import parse_bot_name
from wolf_trading_os.ingestion.option_alpha.fingerprint import (
    FINGERPRINT_VERSION_V2,
    compute_fingerprint_v1,
    compute_fingerprint_v2,
)

# Option Alpha `type` column -> (instrument type, direction, asset class)
_TYPE_MAP: dict[str, tuple[InstrumentType, Direction]] = {
    "iron condor": (InstrumentType.IRON_CONDOR, Direction.CREDIT),
    "iron butterfly": (InstrumentType.IRON_BUTTERFLY, Direction.CREDIT),
    "credit spread": (InstrumentType.VERTICAL_SPREAD, Direction.CREDIT),
    "put credit spread": (InstrumentType.VERTICAL_SPREAD, Direction.CREDIT),
    "call credit spread": (InstrumentType.VERTICAL_SPREAD, Direction.CREDIT),
    "debit spread": (InstrumentType.VERTICAL_SPREAD, Direction.DEBIT),
    "put debit spread": (InstrumentType.VERTICAL_SPREAD, Direction.DEBIT),
    "call debit spread": (InstrumentType.VERTICAL_SPREAD, Direction.DEBIT),
    "long call": (InstrumentType.SINGLE_OPTION, Direction.LONG),
    "long put": (InstrumentType.SINGLE_OPTION, Direction.LONG),
    "short call": (InstrumentType.SINGLE_OPTION, Direction.SHORT),
    "short put": (InstrumentType.SINGLE_OPTION, Direction.SHORT),
    "covered call": (InstrumentType.SINGLE_OPTION, Direction.SHORT),
    "cash secured put": (InstrumentType.SINGLE_OPTION, Direction.SHORT),
    "straddle": (InstrumentType.STRADDLE, Direction.NEUTRAL),
    "strangle": (InstrumentType.STRANGLE, Direction.NEUTRAL),
    "calendar spread": (InstrumentType.CALENDAR_SPREAD, Direction.NEUTRAL),
    "diagonal spread": (InstrumentType.DIAGONAL_SPREAD, Direction.NEUTRAL),
    "long stock": (InstrumentType.STOCK, Direction.LONG),
    "short stock": (InstrumentType.STOCK, Direction.SHORT),
}

_STATUS_MAP: dict[str, TradeStatus] = {
    "open": TradeStatus.OPEN,
    "closed": TradeStatus.CLOSED,
    "expired": TradeStatus.EXPIRED,
    "canceled": TradeStatus.CANCELED,
    "cancelled": TradeStatus.CANCELED,
}


@dataclass
class RowOutcome:
    """Result of normalizing one CSV row."""

    row_number: int  # 1-based data-row number (header excluded)
    trade: CanonicalTrade | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Raw row + legacy fingerprint, kept so the importer can assign
    # per-file occurrence fingerprints and deduplicate against rows
    # imported before the oa2 migration.
    raw_row: dict[str, str | None] = field(default_factory=dict)
    legacy_fingerprint: str | None = None

    @property
    def accepted(self) -> bool:
        return self.trade is not None and not self.errors


def normalize_row(raw_row: dict[str, str | None], row_number: int) -> RowOutcome:
    """Convert one raw (canonical-keyed) CSV row into a CanonicalTrade."""
    outcome = RowOutcome(row_number=row_number, raw_row=dict(raw_row))

    def optional(parser: Any, column: str) -> Any:
        try:
            return parser(raw_row.get(column))
        except ValueError as exc:
            outcome.warnings.append(f"{column}: {exc}")
            return None

    # --- identity-critical fields: reject the row on failure -------------
    symbol = values.clean_str(raw_row.get("symbol"))
    if symbol is None:
        outcome.errors.append("symbol: missing")

    opened_at: dt.datetime | None = None
    try:
        opened_at = values.parse_timestamp(raw_row.get("openDate"))
    except ValueError as exc:
        outcome.errors.append(f"openDate: {exc}")
    if opened_at is None and not outcome.errors:
        outcome.errors.append("openDate: missing")

    quantity: Decimal | None = None
    try:
        quantity = values.parse_decimal(raw_row.get("quantity"))
    except ValueError as exc:
        outcome.errors.append(f"quantity: {exc}")
    if quantity is not None and quantity <= 0:
        outcome.errors.append(f"quantity: must be positive, got {quantity}")

    pnl: Decimal | None = None
    try:
        pnl = values.parse_decimal(raw_row.get("pnl"))
    except ValueError as exc:
        outcome.errors.append(f"pnl: {exc}")

    status_text = values.clean_str(raw_row.get("status"))
    status = (
        _STATUS_MAP.get(status_text.lower(), TradeStatus.UNKNOWN)
        if status_text
        else (TradeStatus.UNKNOWN)
    )
    if pnl is None and status in (TradeStatus.CLOSED, TradeStatus.EXPIRED):
        outcome.errors.append("pnl: missing for closed trade")

    if outcome.errors:
        return outcome

    assert symbol is not None and opened_at is not None

    # --- optional fields: warn on failure, never invent ------------------
    closed_at = optional(values.parse_timestamp, "closeDate")
    expires_at = optional(values.parse_timestamp, "expiration")
    mfe_at = optional(values.parse_timestamp, "highReturnPctDate")
    mae_at = optional(values.parse_timestamp, "lowReturnPctDate")

    entry_price = optional(values.parse_decimal, "openPrice")
    exit_price = optional(values.parse_decimal, "closePrice")
    premium = optional(values.parse_decimal, "premium")
    risk = optional(values.parse_decimal, "risk")
    return_pct = optional(values.parse_decimal, "returnPct")
    return_on_risk = optional(values.parse_decimal, "ror")
    mfe_pct = optional(values.parse_decimal, "highReturnPct")
    mae_pct = optional(values.parse_decimal, "lowReturnPct")
    underlying_open = optional(values.parse_decimal, "underlyingOpen")
    underlying_close = optional(values.parse_decimal, "underlyingClose")
    days_in_trade = optional(values.parse_decimal, "daysInTrade")

    bot_name = values.clean_str(raw_row.get("botName"))
    description = values.clean_str(raw_row.get("description"))
    tags = values.parse_tags(raw_row.get("tags"))

    attrs = parse_bot_name(bot_name)
    parse_sources: dict[str, ParseSource] = dict(attrs.parse_sources)

    # Environment: bot name first, tags as fallback.
    environment = attrs.environment
    if environment is TradeEnvironment.UNKNOWN and tags:
        lowered = {t.lower() for t in tags}
        if "live" in lowered and "paper" not in lowered:
            environment = TradeEnvironment.LIVE
            parse_sources["environment"] = ParseSource.TAGS
        elif "paper" in lowered and "live" not in lowered:
            environment = TradeEnvironment.PAPER
            parse_sources["environment"] = ParseSource.TAGS

    # Instrument classification from the `type` column.
    type_text = values.clean_str(raw_row.get("type"))
    instrument_type, direction = InstrumentType.UNKNOWN, Direction.UNKNOWN
    asset_class = AssetClass.UNKNOWN
    if type_text is not None:
        mapped = _TYPE_MAP.get(type_text.lower())
        if mapped is not None:
            instrument_type, direction = mapped
            asset_class = (
                AssetClass.EQUITY
                if instrument_type is InstrumentType.STOCK
                else AssetClass.EQUITY_OPTION
            )
            parse_sources["instrument_type"] = ParseSource.SOURCE_COLUMN
        else:
            instrument_type = InstrumentType.OTHER
            outcome.warnings.append(f"type: unrecognized {type_text!r}")
    elif expires_at is not None or premium is not None:
        # An expiration or premium implies an option structure.
        asset_class = AssetClass.EQUITY_OPTION
        parse_sources["asset_class"] = ParseSource.DERIVED

    # DTE at entry: derived from expiration and open date, never guessed.
    dte_at_entry: int | None = None
    if expires_at is not None:
        dte_at_entry = (expires_at.date() - opened_at.date()).days
        parse_sources["dte_at_entry"] = ParseSource.DERIVED
        if dte_at_entry < 0:
            outcome.warnings.append(
                f"expiration {expires_at.date()} precedes openDate {opened_at.date()}"
            )

    if closed_at is not None and closed_at < opened_at:
        outcome.errors.append(f"closeDate {closed_at} precedes openDate {opened_at}")
        return outcome

    raw_payload = {k: v for k, v in raw_row.items() if v is not None}

    outcome.legacy_fingerprint = compute_fingerprint_v1(raw_row)
    outcome.trade = CanonicalTrade(
        # occurrence=1 base fingerprint; the importer reassigns the
        # occurrence index for repeated identical rows within one file.
        fingerprint=compute_fingerprint_v2(raw_row),
        fingerprint_version=FINGERPRINT_VERSION_V2,
        source=TradeSource.OPTION_ALPHA,
        strategy_family=attrs.strategy_family,
        strategy_name=attrs.strategy_name,
        strategy_version=attrs.strategy_version,
        bot_name=bot_name,
        environment=environment,
        asset_class=asset_class,
        instrument_type=instrument_type,
        underlying_symbol=symbol.upper(),
        contract_description=description,
        direction=direction,
        status=status,
        quantity=quantity,
        opened_at=opened_at,
        closed_at=closed_at,
        expires_at=expires_at,
        dte_at_entry=dte_at_entry,
        days_in_trade=days_in_trade,
        entry_price=entry_price,
        exit_price=exit_price,
        premium=premium,
        risk=risk,
        realized_pnl=pnl,
        return_pct=return_pct,
        return_on_risk=return_on_risk,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        mfe_at=mfe_at,
        mae_at=mae_at,
        underlying_entry_price=underlying_open,
        underlying_exit_price=underlying_close,
        timeframe=attrs.timeframe,
        target_delta=attrs.target_delta,
        dte_setting=attrs.dte_setting,
        contract_count_setting=attrs.contract_count_setting,
        parse_sources=parse_sources,
        tags=tags,
        raw_payload=raw_payload,
    )
    return outcome
