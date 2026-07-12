"""Persistence helpers for canonical trades and import batches."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from wolf_trading_os.database.orm import ImportBatchRow, TradeRow
from wolf_trading_os.domain import CanonicalTrade


def trade_to_row(trade: CanonicalTrade, import_batch_id: int | None = None) -> TradeRow:
    return TradeRow(
        trade_id=trade.trade_id,
        fingerprint=trade.fingerprint,
        source=trade.source.value,
        import_batch_id=import_batch_id,
        strategy_family=trade.strategy_family,
        strategy_name=trade.strategy_name,
        strategy_version=trade.strategy_version,
        bot_name=trade.bot_name,
        environment=trade.environment.value,
        asset_class=trade.asset_class.value,
        instrument_type=trade.instrument_type.value,
        underlying_symbol=trade.underlying_symbol,
        contract_description=trade.contract_description,
        direction=trade.direction.value,
        status=trade.status.value,
        quantity=trade.quantity,
        opened_at=trade.opened_at,
        closed_at=trade.closed_at,
        expires_at=trade.expires_at,
        dte_at_entry=trade.dte_at_entry,
        days_in_trade=trade.days_in_trade,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        premium=trade.premium,
        risk=trade.risk,
        realized_pnl=trade.realized_pnl,
        return_pct=trade.return_pct,
        return_on_risk=trade.return_on_risk,
        mfe_pct=trade.mfe_pct,
        mae_pct=trade.mae_pct,
        mfe_at=trade.mfe_at,
        mae_at=trade.mae_at,
        underlying_entry_price=trade.underlying_entry_price,
        underlying_exit_price=trade.underlying_exit_price,
        timeframe=trade.timeframe,
        target_delta=trade.target_delta,
        dte_setting=trade.dte_setting,
        contract_count_setting=trade.contract_count_setting,
        parse_sources={k: v.value for k, v in trade.parse_sources.items()},
        tags=list(trade.tags),
        raw_payload=trade.raw_payload,
    )


def existing_fingerprints(session: Session, fingerprints: list[str]) -> set[str]:
    """Return the subset of `fingerprints` already stored."""
    if not fingerprints:
        return set()
    rows = session.execute(
        select(TradeRow.fingerprint).where(TradeRow.fingerprint.in_(fingerprints))
    )
    return {fp for (fp,) in rows}


def create_import_batch(
    session: Session,
    *,
    source: str,
    filename: str,
    file_sha256: str,
) -> ImportBatchRow:
    batch = ImportBatchRow(source=source, filename=filename, file_sha256=file_sha256)
    session.add(batch)
    session.flush()  # assign id
    return batch


def finalize_import_batch(
    batch: ImportBatchRow,
    *,
    rows_received: int,
    rows_accepted: int,
    rows_rejected: int,
    rows_duplicate: int,
    warnings: list[dict[str, Any]],
) -> None:
    batch.rows_received = rows_received
    batch.rows_accepted = rows_accepted
    batch.rows_rejected = rows_rejected
    batch.rows_duplicate = rows_duplicate
    batch.warnings = warnings
