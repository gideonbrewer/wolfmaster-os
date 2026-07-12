"""Possible-correction detection for corrected re-exports (H6)."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from wolf_trading_os.database.orm import TradeRow
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


def _sample_lines() -> list[str]:
    return (FIXTURES / "option_alpha_sample.csv").read_text().splitlines()


def _mutate_row(line: str, header: str, **overrides: str) -> str:
    columns = header.split(",")
    cells = next(csv.reader(io.StringIO(line)))
    for column, value in overrides.items():
        cells[columns.index(column)] = value
    buf = io.StringIO()
    csv.writer(buf).writerow(cells)
    return buf.getvalue().strip("\r\n")


class TestCorrectionDetection:
    def test_corrected_pnl_warns_and_keeps_both(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        importer = OptionAlphaImporter(clean_database)
        original = tmp_path / "orig.csv"
        original.write_text("\n".join([lines[0], lines[1]]) + "\n")
        importer.import_files([original])

        corrected_row = _mutate_row(lines[1], lines[0], pnl="395.00", ror="0.6124")
        corrected = tmp_path / "corrected.csv"
        corrected.write_text("\n".join([lines[0], corrected_row]) + "\n")
        result = importer.import_files([corrected]).files[0]

        assert result.rows_accepted == 1  # stored, never merged/overwritten
        assert _count_trades(clean_database) == 2
        assert len(result.possible_corrections) == 1
        correction = result.possible_corrections[0]
        assert "realized_pnl" in correction.differing_fields
        assert correction.existing_fingerprint != correction.new_fingerprint
        assert any("possible_correction" in w for w in result.file_warnings)

    def test_changed_exit_price_warns(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        importer = OptionAlphaImporter(clean_database)
        original = tmp_path / "orig.csv"
        original.write_text("\n".join([lines[0], lines[1]]) + "\n")
        importer.import_files([original])

        changed = _mutate_row(lines[1], lines[0], closePrice="0.90")
        f = tmp_path / "changed.csv"
        f.write_text("\n".join([lines[0], changed]) + "\n")
        result = importer.import_files([f]).files[0]
        assert len(result.possible_corrections) == 1
        assert "exit_price" in result.possible_corrections[0].differing_fields

    def test_different_open_time_is_a_separate_trade(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        importer = OptionAlphaImporter(clean_database)
        original = tmp_path / "orig.csv"
        original.write_text("\n".join([lines[0], lines[1]]) + "\n")
        importer.import_files([original])

        separate = _mutate_row(lines[1], lines[0], openDate="01/05/26 10:35", pnl="100.00")
        f = tmp_path / "separate.csv"
        f.write_text("\n".join([lines[0], separate]) + "\n")
        result = importer.import_files([f]).files[0]
        assert result.rows_accepted == 1
        assert result.possible_corrections == []

    def test_reimporting_corrected_export_is_duplicate_not_new_correction(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        importer = OptionAlphaImporter(clean_database)
        original = tmp_path / "orig.csv"
        original.write_text("\n".join([lines[0], lines[1]]) + "\n")
        importer.import_files([original])

        corrected_row = _mutate_row(lines[1], lines[0], pnl="395.00")
        corrected = tmp_path / "corrected.csv"
        corrected.write_text("\n".join([lines[0], corrected_row]) + "\n")
        importer.import_files([corrected])

        result = importer.import_files([corrected]).files[0]
        assert result.rows_accepted == 0
        assert result.rows_duplicate == 1
        assert result.possible_corrections == []
        assert _count_trades(clean_database) == 2

    def test_identical_occurrence_twins_are_not_corrections(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        f = tmp_path / "twins.csv"
        f.write_text("\n".join([lines[0], lines[1], lines[1]]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.rows_accepted == 2
        assert result.possible_corrections == []  # identical, not corrected
