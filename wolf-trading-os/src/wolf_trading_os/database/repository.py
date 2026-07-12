"""Persistence helpers for canonical trades and import batches.

Trade insertion is conflict-safe: PostgreSQL ``INSERT ... ON CONFLICT
(fingerprint) DO NOTHING RETURNING fingerprint`` makes the database the
final duplicate arbiter, so concurrent imports of the same file cannot
raise IntegrityError — the losing insert is simply reported as a
duplicate.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from wolf_trading_os.database.orm import ImportBatchRow, TradeRow
from wolf_trading_os.domain import CanonicalTrade


def trade_to_values(trade: CanonicalTrade, import_batch_id: int | None = None) -> dict[str, Any]:
    """Column values for one canonical trade (used for bulk insert)."""
    return {
        "trade_id": trade.trade_id,
        "fingerprint": trade.fingerprint,
        "fingerprint_version": trade.fingerprint_version,
        "source": trade.source.value,
        "import_batch_id": import_batch_id,
        "strategy_family": trade.strategy_family,
        "strategy_name": trade.strategy_name,
        "strategy_version": trade.strategy_version,
        "bot_name": trade.bot_name,
        "environment": trade.environment.value,
        "asset_class": trade.asset_class.value,
        "instrument_type": trade.instrument_type.value,
        "underlying_symbol": trade.underlying_symbol,
        "contract_description": trade.contract_description,
        "direction": trade.direction.value,
        "status": trade.status.value,
        "quantity": trade.quantity,
        "opened_at": trade.opened_at,
        "closed_at": trade.closed_at,
        "expires_at": trade.expires_at,
        "dte_at_entry": trade.dte_at_entry,
        "days_in_trade": trade.days_in_trade,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "premium": trade.premium,
        "risk": trade.risk,
        "realized_pnl": trade.realized_pnl,
        "return_fraction": trade.return_fraction,
        "return_on_risk": trade.return_on_risk,
        "mfe_fraction": trade.mfe_fraction,
        "mae_fraction": trade.mae_fraction,
        "mfe_at": trade.mfe_at,
        "mae_at": trade.mae_at,
        "underlying_entry_price": trade.underlying_entry_price,
        "underlying_exit_price": trade.underlying_exit_price,
        "timeframe": trade.timeframe,
        "target_delta": trade.target_delta,
        "dte_setting": trade.dte_setting,
        "contract_count_setting": trade.contract_count_setting,
        "parse_sources": {k: v.value for k, v in trade.parse_sources.items()},
        "tags": list(trade.tags),
        "raw_payload": trade.raw_payload,
    }


def insert_trades_on_conflict(
    session: Session,
    trades: list[CanonicalTrade],
    import_batch_id: int,
) -> set[str]:
    """Insert trades; return the set of fingerprints actually inserted.

    Fingerprints not returned already existed (concurrent or prior
    import) and must be counted as duplicates by the caller.
    """
    if not trades:
        return set()
    stmt = (
        pg_insert(TradeRow)
        .values([trade_to_values(t, import_batch_id) for t in trades])
        .on_conflict_do_nothing(index_elements=["fingerprint"])
        .returning(TradeRow.fingerprint)
    )
    return {fp for (fp,) in session.execute(stmt)}


def existing_fingerprints(
    session: Session, fingerprints: list[str], version: str | None = None
) -> set[str]:
    """Return the subset of `fingerprints` already stored (optionally
    restricted to one fingerprint_version, e.g. legacy 'oa1' rows)."""
    if not fingerprints:
        return set()
    query = select(TradeRow.fingerprint).where(TradeRow.fingerprint.in_(fingerprints))
    if version is not None:
        query = query.where(TradeRow.fingerprint_version == version)
    return {fp for (fp,) in session.execute(query)}


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


def find_possible_corrections(
    session: Session,
    trades: list[CanonicalTrade],
) -> list[dict[str, Any]]:
    """Detect stored trades that a newly inserted trade may CORRECT (H6).

    Candidate-correction identity (documented in data-model.md): source,
    bot_name, underlying_symbol, contract_description, expires_at,
    opened_at, quantity. When an existing row shares that identity but a
    different fingerprint AND differs materially (closed_at, exit_price,
    realized_pnl, return_fraction, mfe_fraction, mae_fraction, status),
    both records are kept and a `possible_correction` warning is
    emitted. Records are never silently merged or deleted; full
    supersession/versioning is deferred (docs/roadmap.md).
    """
    material_fields = (
        "closed_at",
        "exit_price",
        "realized_pnl",
        "return_fraction",
        "mfe_fraction",
        "mae_fraction",
        "status",
    )
    corrections: list[dict[str, Any]] = []
    for trade in trades:
        rows = session.execute(
            select(TradeRow).where(
                TradeRow.source == trade.source.value,
                TradeRow.bot_name.is_(trade.bot_name)
                if trade.bot_name is None
                else TradeRow.bot_name == trade.bot_name,
                TradeRow.underlying_symbol == trade.underlying_symbol,
                TradeRow.contract_description.is_(trade.contract_description)
                if trade.contract_description is None
                else TradeRow.contract_description == trade.contract_description,
                TradeRow.expires_at.is_(trade.expires_at)
                if trade.expires_at is None
                else TradeRow.expires_at == trade.expires_at,
                TradeRow.opened_at == trade.opened_at,
                TradeRow.quantity == trade.quantity,
                TradeRow.fingerprint != trade.fingerprint,
            )
        ).scalars()
        for row in rows:
            differing = []
            for field in material_fields:
                stored = getattr(row, field)
                incoming = getattr(trade, field)
                if field == "status":
                    incoming = trade.status.value
                if stored != incoming:
                    differing.append(field)
            if differing:
                corrections.append(
                    {
                        "existing_trade_id": str(row.trade_id),
                        "existing_fingerprint": row.fingerprint,
                        "new_fingerprint": trade.fingerprint,
                        "differing_fields": differing,
                    }
                )
    return corrections
