"""End-to-end import flow against a real PostgreSQL database."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from wolf_trading_os.database.orm import ImportBatchRow, TradeRow
from wolf_trading_os.ingestion.option_alpha import OptionAlphaImporter

FIXTURES = Path(__file__).parents[1] / "fixtures"

pytestmark = pytest.mark.integration


def _count_trades(db_url: str) -> int:
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(TradeRow)).scalar_one())
    finally:
        engine.dispose()


class TestValidImport:
    def test_sample_imports_fully(self, clean_database: str) -> None:
        importer = OptionAlphaImporter(clean_database)
        summary = importer.import_files([FIXTURES / "option_alpha_sample.csv"])
        assert summary.rows_received == 12
        assert summary.rows_accepted == 12
        assert summary.rows_rejected == 0
        assert summary.rows_duplicate == 0
        assert _count_trades(clean_database) == 12

    def test_fields_persisted_roundtrip(self, clean_database: str) -> None:
        OptionAlphaImporter(clean_database).import_files([FIXTURES / "option_alpha_sample.csv"])
        engine = create_engine(clean_database)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    select(TradeRow).where(
                        TradeRow.contract_description == "SPY Jan 5 2026 $595 Iron Butterfly"
                    )
                ).one()
        finally:
            engine.dispose()
        assert row.underlying_symbol == "SPY"
        assert row.quantity == Decimal("3")
        assert row.realized_pnl == Decimal("390.00")
        assert row.strategy_family == "Hulk"
        assert row.target_delta == Decimal("0.5")
        assert row.dte_setting == 0
        assert row.environment == "live"
        assert row.instrument_type == "iron_butterfly"
        assert row.raw_payload["pnl"] == "390.00"
        assert row.tags == ["0dte", "momentum"]

    def test_import_batch_audit_row(self, clean_database: str) -> None:
        OptionAlphaImporter(clean_database).import_files([FIXTURES / "option_alpha_sample.csv"])
        engine = create_engine(clean_database)
        try:
            with engine.connect() as conn:
                batch = conn.execute(select(ImportBatchRow)).one()
        finally:
            engine.dispose()
        assert batch.rows_received == 12
        assert batch.rows_accepted == 12
        assert batch.filename == "option_alpha_sample.csv"
        assert len(batch.file_sha256) == 64


class TestDuplicatePrevention:
    def test_reimport_creates_no_duplicates(self, clean_database: str) -> None:
        importer = OptionAlphaImporter(clean_database)
        importer.import_files([FIXTURES / "option_alpha_sample.csv"])
        summary = importer.import_files([FIXTURES / "option_alpha_sample.csv"])
        assert summary.rows_accepted == 0
        assert summary.rows_duplicate == 12
        assert _count_trades(clean_database) == 12

    def test_overlapping_file_partially_deduplicates(self, clean_database: str) -> None:
        importer = OptionAlphaImporter(clean_database)
        importer.import_files([FIXTURES / "option_alpha_sample.csv"])
        summary = importer.import_files([FIXTURES / "option_alpha_overlap.csv"])
        assert summary.rows_received == 4
        assert summary.rows_accepted == 2  # two rows overlap with sample
        assert summary.rows_duplicate == 2
        assert _count_trades(clean_database) == 14

    def test_multiple_files_one_call(self, clean_database: str) -> None:
        summary = OptionAlphaImporter(clean_database).import_files(
            [
                FIXTURES / "option_alpha_sample.csv",
                FIXTURES / "option_alpha_overlap.csv",
            ]
        )
        assert summary.rows_received == 16
        assert summary.rows_accepted == 14
        assert summary.rows_duplicate == 2
        assert _count_trades(clean_database) == 14

    def test_repeated_rows_within_single_file_are_distinct_trades(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        # Identical rows inside ONE export are genuinely separate trades
        # (occurrence-indexed fingerprints); re-importing the same file
        # still deduplicates. See ADR-016.
        source = (FIXTURES / "option_alpha_overlap.csv").read_text()
        lines = source.strip().splitlines()
        doubled = "\n".join([lines[0], *lines[1:], *lines[1:]]) + "\n"
        target = tmp_path / "doubled.csv"
        target.write_text(doubled)
        importer = OptionAlphaImporter(clean_database)
        summary = importer.import_files([target])
        assert summary.rows_received == 8
        assert summary.rows_accepted == 8
        assert summary.rows_duplicate == 0
        assert any("repeated identical source rows" in w for w in summary.files[0].file_warnings)
        resummary = importer.import_files([target])
        assert resummary.rows_accepted == 0
        assert resummary.rows_duplicate == 8


class TestMalformedInput:
    def test_malformed_rows_reported_not_fatal(self, clean_database: str) -> None:
        summary = OptionAlphaImporter(clean_database).import_files(
            [FIXTURES / "option_alpha_malformed.csv"]
        )
        result = summary.files[0]
        assert result.ok
        assert result.rows_received == 6
        assert result.rows_accepted == 2  # 1 clean + 1 warned (bad optional field)
        assert result.rows_rejected == 4
        reasons = {msg for issue in result.rejected_rows for msg in issue.messages}
        assert any("symbol" in r for r in reasons)
        assert any("openDate" in r for r in reasons)
        assert any("quantity" in r for r in reasons)
        assert any("pnl" in r for r in reasons)
        assert _count_trades(clean_database) == 2

    def test_missing_required_columns_rejects_file(self, clean_database: str) -> None:
        summary = OptionAlphaImporter(clean_database).import_files(
            [FIXTURES / "option_alpha_missing_columns.csv"]
        )
        result = summary.files[0]
        assert not result.ok
        assert result.error is not None and "missing required columns" in result.error
        assert "pnl" in result.error and "quantity" in result.error
        assert _count_trades(clean_database) == 0

    def test_empty_file_rejected(self, clean_database: str, tmp_path: Path) -> None:
        empty = tmp_path / "empty.csv"
        empty.write_text("")
        summary = OptionAlphaImporter(clean_database).import_files([empty])
        assert not summary.files[0].ok
        assert summary.files[0].error == "empty file"
