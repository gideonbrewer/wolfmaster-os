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
    insert_trades_on_conflict,
)
from wolf_trading_os.domain import CanonicalTrade, TradeSource
from wolf_trading_os.ingestion.option_alpha.fingerprint import compute_fingerprint_v2
from wolf_trading_os.ingestion.option_alpha.normalizer import RowOutcome, normalize_row
from wolf_trading_os.ingestion.option_alpha.schema import missing_required, normalize_headers
from wolf_trading_os.logging import get_logger

logger = get_logger(__name__)


class RowIssue(BaseModel):
    """One rejected row or one warning attached to an accepted row."""

    row_number: int
    messages: list[str]


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

    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url

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

        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")

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

        outcomes: list[RowOutcome] = []
        for row_number, cells in enumerate(reader, start=1):
            if not any(cell.strip() for cell in cells):
                continue  # skip fully blank lines
            raw_row: dict[str, str | None] = {
                column: (cells[i] if i < len(cells) else None)
                for i, column in index_to_column.items()
            }
            outcomes.append(normalize_row(raw_row, row_number))

        result.rows_received = len(outcomes)

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
        for trade in to_insert:
            if trade.fingerprint in inserted:
                result.rows_accepted += 1
            else:
                result.rows_duplicate += 1
