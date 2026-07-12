"""Option Alpha CSV import service.

Accepts one or multiple CSV files (paths or binary buffers), validates and
normalizes rows, deduplicates against the database and within the batch,
persists canonical trades, and returns a full summary. Malformed rows are
reported without aborting the import.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from wolf_trading_os.database import session_scope
from wolf_trading_os.database.repository import (
    create_import_batch,
    existing_fingerprints,
    finalize_import_batch,
    find_possible_corrections,
    insert_trades_on_conflict,
)
from wolf_trading_os.domain import CanonicalTrade, TradeSource
from wolf_trading_os.ingestion.option_alpha.fingerprint import compute_fingerprint_v2
from wolf_trading_os.ingestion.option_alpha.normalizer import RowOutcome, normalize_row
from wolf_trading_os.ingestion.option_alpha.schema import missing_required, normalize_headers
from wolf_trading_os.ingestion.option_alpha.values import DateOrder, slash_date_order_evidence
from wolf_trading_os.logging import get_logger

logger = get_logger(__name__)


class RowIssue(BaseModel):
    """One rejected row or one warning attached to an accepted row."""

    row_number: int
    messages: list[str]


class PossibleCorrection(BaseModel):
    """A newly imported trade that may be a corrected re-export of an
    existing stored trade (H6). Both records are kept; nothing is
    merged or deleted automatically."""

    existing_trade_id: str
    existing_fingerprint: str
    new_fingerprint: str
    differing_fields: list[str]


class FileImportResult(BaseModel):
    filename: str
    file_sha256: str
    ok: bool = True
    error: str | None = None  # file-level failure (e.g. missing columns)
    rows_received: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rows_duplicate: int = 0
    rejected_rows: list[RowIssue] = Field(default_factory=list)
    warnings: list[RowIssue] = Field(default_factory=list)
    file_warnings: list[str] = Field(default_factory=list)
    possible_corrections: list[PossibleCorrection] = Field(default_factory=list)
    unknown_columns: list[str] = Field(default_factory=list)


class ImportSummary(BaseModel):
    files: list[FileImportResult] = Field(default_factory=list)

    @property
    def rows_received(self) -> int:
        return sum(f.rows_received for f in self.files)

    @property
    def rows_accepted(self) -> int:
        return sum(f.rows_accepted for f in self.files)

    @property
    def rows_rejected(self) -> int:
        return sum(f.rows_rejected for f in self.files)

    @property
    def rows_duplicate(self) -> int:
        return sum(f.rows_duplicate for f in self.files)

    def as_report(self) -> dict[str, object]:
        return {
            "rows_received": self.rows_received,
            "rows_accepted": self.rows_accepted,
            "rows_rejected": self.rows_rejected,
            "rows_duplicate": self.rows_duplicate,
            "files": [f.model_dump() for f in self.files],
        }


class OptionAlphaImporter:
    """Imports Option Alpha CSV exports into the canonical trades table."""

    def __init__(
        self,
        database_url: str | None = None,
        date_order: DateOrder = "MDY",
    ) -> None:
        """``date_order`` is the file-level slash-date convention. "MDY"
        is the confirmed Option Alpha export format; pass "DMY" for
        day-first exports. Contradictory in-file evidence rejects the
        file (never guessed per-cell)."""
        self._database_url = database_url
        self._date_order = date_order

    def import_files(self, paths: Sequence[str | Path]) -> ImportSummary:
        """Import one or multiple CSV files by path."""
        summary = ImportSummary()
        for path in paths:
            path = Path(path)
            data = path.read_bytes()
            summary.files.append(self._import_bytes(data, filename=path.name))
        return summary

    def import_buffer(self, buffer: BinaryIO, filename: str) -> ImportSummary:
        """Import a single already-open binary buffer (e.g. Streamlit upload)."""
        return ImportSummary(files=[self._import_bytes(buffer.read(), filename=filename)])

    # ------------------------------------------------------------------

    def _import_bytes(self, data: bytes, filename: str) -> FileImportResult:
        file_sha256 = hashlib.sha256(data).hexdigest()
        result = FileImportResult(filename=filename, file_sha256=file_sha256)
        log = logger.bind(filename=filename, file_sha256=file_sha256)

        text_or_error = _decode_csv_bytes(data)
        if isinstance(text_or_error, FileEncodingError):
            result.ok = False
            result.error = text_or_error.message
            log.warning("import_file_rejected", reason=result.error)
            return result
        text = text_or_error

        reader = csv.reader(io.StringIO(text))
        try:
            headers = next(reader)
        except StopIteration:
            result.ok = False
            result.error = "empty file"
            log.warning("import_file_rejected", reason=result.error)
            return result

        index_to_column, unknown = normalize_headers(headers)
        result.unknown_columns = unknown
        missing = missing_required(set(index_to_column.values()))
        if missing:
            result.ok = False
            result.error = f"missing required columns: {', '.join(sorted(missing))}"
            log.warning("import_file_rejected", reason=result.error)
            return result

        raw_rows: list[dict[str, str | None]] = []
        for cells in reader:
            if not any(cell.strip() for cell in cells):
                continue  # skip fully blank lines
            raw_rows.append(
                {
                    column: (cells[i] if i < len(cells) else None)
                    for i, column in index_to_column.items()
                }
            )

        conflict = _scan_date_order_conflicts(raw_rows, self._date_order)
        if conflict is not None:
            result.ok = False
            result.error = conflict
            log.warning("import_file_rejected", reason=result.error)
            return result

        outcomes: list[RowOutcome] = [
            normalize_row(raw_row, row_number, self._date_order)
            for row_number, raw_row in enumerate(raw_rows, start=1)
        ]
        result.rows_received = len(outcomes)

        unit_error = _check_return_unit_convention(outcomes, result)
        if unit_error is not None:
            result.ok = False
            result.error = unit_error
            log.warning("import_file_rejected", reason=result.error)
            return result

        try:
            with session_scope(self._database_url) as session:
                batch = create_import_batch(
                    session,
                    source=TradeSource.OPTION_ALPHA.value,
                    filename=filename,
                    file_sha256=file_sha256,
                )
                self._persist_outcomes(session, outcomes, result, batch_id=batch.id)
                finalize_import_batch(
                    batch,
                    rows_received=result.rows_received,
                    rows_accepted=result.rows_accepted,
                    rows_rejected=result.rows_rejected,
                    rows_duplicate=result.rows_duplicate,
                    warnings=[w.model_dump() for w in result.warnings],
                )
        except SQLAlchemyError as exc:
            # Secondary safety layer: application-level validation should
            # prevent this. Never surface a raw stack trace or anything
            # containing the connection URL to the caller.
            log.error(
                "import_database_error",
                error_type=type(exc).__name__,
                rows_received=result.rows_received,
            )
            result.ok = False
            result.rows_accepted = 0
            result.rows_duplicate = 0
            result.error = (
                f"database error while importing ({type(exc).__name__}); "
                "the file was rolled back and no rows were stored"
            )
            return result

        log.info(
            "import_file_complete",
            rows_received=result.rows_received,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
            rows_duplicate=result.rows_duplicate,
        )
        return result

    @staticmethod
    def _persist_outcomes(
        session: Session,
        outcomes: list[RowOutcome],
        result: FileImportResult,
        batch_id: int,
    ) -> None:
        accepted = [o for o in outcomes if o.accepted]
        for outcome in outcomes:
            if not outcome.accepted:
                result.rows_rejected += 1
                result.rejected_rows.append(
                    RowIssue(row_number=outcome.row_number, messages=outcome.errors)
                )
            elif outcome.warnings:
                result.warnings.append(
                    RowIssue(row_number=outcome.row_number, messages=outcome.warnings)
                )

        # -- occurrence assignment: repeated identical rows within one file
        # are genuinely distinct trades and get deterministic occ=k
        # fingerprints (see fingerprint.py).
        occurrence_counts: dict[str, int] = {}
        candidates: list[tuple[CanonicalTrade, int]] = []
        legacy_fps: list[str] = []
        repeated_groups: set[str] = set()
        for outcome in accepted:
            trade = outcome.trade
            assert trade is not None
            base = trade.fingerprint  # occurrence=1 fingerprint
            k = occurrence_counts.get(base, 0) + 1
            occurrence_counts[base] = k
            if k > 1:
                repeated_groups.add(base)
                trade = trade.model_copy(
                    update={"fingerprint": compute_fingerprint_v2(outcome.raw_row, occurrence=k)}
                )
            candidates.append((trade, k))
            if outcome.legacy_fingerprint is not None:
                legacy_fps.append(outcome.legacy_fingerprint)

        if repeated_groups:
            result.file_warnings.append(
                f"repeated identical source rows detected in {len(repeated_groups)} "
                "group(s); each occurrence was preserved as a separate trade"
            )

        # -- legacy dedup: rows imported before the oa2 migration carry oa1
        # fingerprints; match against them so old databases don't
        # double-import on re-import.
        stored_legacy = existing_fingerprints(session, legacy_fps, version="oa1")
        to_insert: list[CanonicalTrade] = []
        for outcome, (trade, occurrence) in zip(accepted, candidates, strict=True):
            # Legacy oa1 dedup applies only to occurrence 1: the oa1
            # algorithm stored at most one copy of identical rows, so
            # later occurrences were never stored and must insert.
            if (
                occurrence == 1
                and outcome.legacy_fingerprint is not None
                and outcome.legacy_fingerprint in stored_legacy
            ):
                result.rows_duplicate += 1
            else:
                to_insert.append(trade)

        # -- conflict-safe insert: the UNIQUE constraint is the final
        # arbiter; losing a race to a concurrent import means "duplicate",
        # never an exception.
        inserted = insert_trades_on_conflict(session, to_insert, batch_id)
        inserted_trades = []
        for trade in to_insert:
            if trade.fingerprint in inserted:
                result.rows_accepted += 1
                inserted_trades.append(trade)
            else:
                result.rows_duplicate += 1

        # Possible-correction detection (H6): newly inserted trades that
        # share candidate identity with an existing row but differ
        # materially. Re-imports of the corrected file are duplicates and
        # never reach this check again.
        for correction in find_possible_corrections(session, inserted_trades):
            result.possible_corrections.append(PossibleCorrection(**correction))
        if result.possible_corrections:
            result.file_warnings.append(
                f"possible_correction: {len(result.possible_corrections)} newly "
                "imported trade(s) match an existing trade's identity but differ "
                "materially — both records were kept (see possible_corrections)"
            )


# --------------------------------------------------------------------------
# file-level validation helpers


class FileEncodingError:
    """A file-level encoding rejection (returned, not raised)."""

    def __init__(self, message: str) -> None:
        self.message = message


_BOM_ENCODINGS: tuple[tuple[bytes, str], ...] = (
    # Order matters: UTF-32 LE BOM starts with the UTF-16 LE BOM bytes.
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)


def _decode_csv_bytes(data: bytes) -> str | FileEncodingError:
    """Decode CSV bytes with BOM detection (M6).

    UTF-8 (with or without BOM), UTF-16 LE/BE and UTF-32 LE/BE are
    decoded properly. Undecodable input falls back to latin-1 as a
    documented last resort, but any text still containing NUL bytes is
    rejected at the FILE level — a mis-decoded wide encoding must never
    degrade into dozens of confusing row-level errors.
    """
    for bom, encoding in _BOM_ENCODINGS:
        if data.startswith(bom):
            try:
                text = data.decode(encoding)
            except UnicodeDecodeError:
                return FileEncodingError(
                    f"file has a {encoding} byte-order mark but could not be decoded as {encoding}"
                )
            return _reject_nuls(text)
    try:
        return _reject_nuls(data.decode("utf-8"))
    except UnicodeDecodeError:
        pass
    # Documented last-resort fallback for legacy single-byte exports.
    return _reject_nuls(data.decode("latin-1"))


def _reject_nuls(text: str) -> str | FileEncodingError:
    if "\x00" in text:
        return FileEncodingError(
            "file contains NUL bytes — it is not valid text in a supported "
            "encoding (UTF-8, UTF-16, UTF-32, latin-1); re-export as UTF-8"
        )
    return text


_DATE_COLUMNS = ("openDate", "closeDate", "expiration", "highReturnPctDate", "lowReturnPctDate")


def _scan_date_order_conflicts(
    raw_rows: list[dict[str, str | None]], date_order: DateOrder
) -> str | None:
    """Reject the file when any slash date PROVES the other date order (M4).

    Cells valid under both orders are interpreted per the configured
    order; cells valid only under the opposite order are contradictory
    evidence and fail the whole file closed.
    """
    for row_number, raw_row in enumerate(raw_rows, start=1):
        for column in _DATE_COLUMNS:
            evidence = slash_date_order_evidence(raw_row.get(column))
            if evidence is not None and evidence != date_order:
                other = "day-first (DMY)" if evidence == "DMY" else "month-first (MDY)"
                return (
                    f"date-order conflict: row {row_number} column {column} "
                    f"value {raw_row.get(column)!r} is only valid as {other}, "
                    f"but this import is configured as {date_order}; "
                    "re-run with the correct --date-order"
                )
    return None


# Return-unit validation (M3): ror should approximate pnl / risk when all
# three are present. Ratios near 100 across a file mean the export is in
# percentage points, not the documented decimal fractions -> fail closed.
_UNIT_RATIO_TOLERANCE = (0.8, 1.2)
_UNIT_PERCENT_BAND = (80.0, 120.0)
_MIN_COMPARABLE_ROWS = 3


def _check_return_unit_convention(
    outcomes: list[RowOutcome], result: FileImportResult
) -> str | None:
    ratios: list[tuple[int, float]] = []
    for outcome in outcomes:
        trade = outcome.trade
        if trade is None or None in (trade.return_on_risk, trade.realized_pnl, trade.risk):
            continue
        assert trade.risk is not None and trade.realized_pnl is not None
        assert trade.return_on_risk is not None
        if trade.risk == 0:
            continue
        implied = float(trade.realized_pnl) / float(trade.risk)
        if abs(implied) < 0.005:
            continue  # too small for a meaningful ratio
        ratios.append((outcome.row_number, float(trade.return_on_risk) / implied))

    if not ratios:
        return None

    percentish = [r for _, r in ratios if _UNIT_PERCENT_BAND[0] <= abs(r) <= _UNIT_PERCENT_BAND[1]]
    if len(ratios) >= _MIN_COMPARABLE_ROWS and len(percentish) >= 0.8 * len(ratios):
        return (
            "return-unit mismatch: ror/returnPct values are ~100x the "
            "P&L/risk ratio across the file — the export appears to use "
            "percentage points, but this importer requires Option Alpha's "
            "decimal-fraction convention (0.125 == 12.5%). No silent 100x "
            "adjustment is applied; verify the export format"
        )

    for row_number, ratio in ratios:
        if not (_UNIT_RATIO_TOLERANCE[0] <= ratio <= _UNIT_RATIO_TOLERANCE[1]):
            result.warnings.append(
                RowIssue(
                    row_number=row_number,
                    messages=[
                        f"ror inconsistent with pnl/risk (ratio {ratio:.2f}); "
                        "value kept as exported"
                    ],
                )
            )
    return None
