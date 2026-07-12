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
from sqlalchemy.orm import Session

from wolf_trading_os.database import session_scope
from wolf_trading_os.database.repository import (
    create_import_batch,
    existing_fingerprints,
    finalize_import_batch,
    trade_to_row,
)
from wolf_trading_os.domain import TradeSource
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

        fingerprints = [o.trade.fingerprint for o in accepted if o.trade is not None]
        already_stored = existing_fingerprints(session, fingerprints)

        seen_in_batch: set[str] = set()
        for outcome in accepted:
            trade = outcome.trade
            assert trade is not None
            if trade.fingerprint in already_stored or trade.fingerprint in seen_in_batch:
                result.rows_duplicate += 1
                continue
            seen_in_batch.add(trade.fingerprint)
            session.add(trade_to_row(trade, import_batch_id=batch_id))
            result.rows_accepted += 1
