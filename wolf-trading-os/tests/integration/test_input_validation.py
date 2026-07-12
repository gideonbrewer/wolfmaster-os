"""File-level input validation: numeric ranges, units, dates, encodings.

Remediation tests for audit findings H3 (range validation), M3 (return
unit convention), M4 (date-order ambiguity), and M6 (encoding).
"""

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


class TestNumericRangeValidation:
    """H3: out-of-range values reject the row, never the file."""

    @pytest.mark.parametrize(
        ("column", "value", "expect_row_rejected"),
        [
            ("pnl", "99999999999999999999999", True),  # overflow -> reject row
            ("pnl", "NaN", True),  # NaN pnl on closed trade -> missing -> reject
            ("pnl", "Infinity", True),
            ("quantity", "-3", True),
            ("quantity", "0", True),
            ("quantity", "3.123456789012", True),  # not plain? it is plain; in range -> accepted
        ],
    )
    def test_bad_value_rejects_only_that_row(
        self,
        clean_database: str,
        tmp_path: Path,
        column: str,
        value: str,
        expect_row_rejected: bool,
    ) -> None:
        lines = _sample_lines()
        bad = _mutate_row(lines[2], lines[0], **{column: value})
        f = tmp_path / "mixed.csv"
        f.write_text("\n".join([lines[0], lines[1], bad]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.ok, result.error
        if column == "quantity" and value == "3.123456789012":
            # excessive precision within NUMERIC(20,8) range: accepted
            # (PostgreSQL rounds to column scale).
            assert result.rows_accepted == 2
            assert result.rows_rejected == 0
        else:
            assert result.rows_accepted == 1  # the good row imported
            assert result.rows_rejected == 1
            reason = "; ".join(m for r in result.rejected_rows for m in r.messages)
            assert column in reason or "pnl" in reason
        assert _count_trades(clean_database) == result.rows_accepted

    def test_overflow_names_field_and_value(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        bad = _mutate_row(lines[1], lines[0], pnl="99999999999999999999999")
        f = tmp_path / "overflow.csv"
        f.write_text("\n".join([lines[0], bad]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        messages = [m for r in result.rejected_rows for m in r.messages]
        assert any("realized_pnl" in m and "out of range" in m for m in messages), messages

    def test_huge_underlying_price_warns_and_nulls(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        bad = _mutate_row(lines[1], lines[0], underlyingOpen="9999999999999.99")
        f = tmp_path / "hugeunderlying.csv"
        f.write_text("\n".join([lines[0], bad]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        # Optional field: row accepted, value nulled with a warning.
        assert result.rows_accepted == 1
        assert any("underlyingOpen" in m for w in result.warnings for m in w.messages), (
            result.warnings
        )

    def test_negative_risk_warns_and_nulls(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        bad = _mutate_row(lines[1], lines[0], risk="-645.00")
        f = tmp_path / "negrisk.csv"
        f.write_text("\n".join([lines[0], bad]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.rows_accepted == 1
        assert any("risk" in m for w in result.warnings for m in w.messages)

    def test_negative_premium_is_valid_debit(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        row = _mutate_row(lines[1], lines[0], premium="-645.00")
        f = tmp_path / "debit.csv"
        f.write_text("\n".join([lines[0], row]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.rows_accepted == 1
        assert not result.warnings


class TestReturnUnitConvention:
    """M3: percent-point files fail closed; no silent 100x adjustment."""

    def test_fraction_format_file_imports_cleanly(self, clean_database: str) -> None:
        result = (
            OptionAlphaImporter(clean_database)
            .import_files([FIXTURES / "option_alpha_sample.csv"])
            .files[0]
        )
        assert result.ok
        assert result.rows_accepted == 12
        assert not result.warnings  # all ror values consistent with pnl/risk

    def test_percent_point_file_rejected(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        header = lines[0]
        converted = [header]
        for line in lines[1:]:
            cells = next(csv.reader(io.StringIO(line)))
            for col in ("ror", "returnPct", "highReturnPct", "lowReturnPct"):
                i = header.split(",").index(col)
                if cells[i].strip():
                    cells[i] = str(float(cells[i]) * 100)  # fractions -> percent points
            buf = io.StringIO()
            csv.writer(buf).writerow(cells)
            converted.append(buf.getvalue().strip("\r\n"))
        f = tmp_path / "percentpoints.csv"
        f.write_text("\n".join(converted) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert not result.ok
        assert result.error is not None and "return-unit mismatch" in result.error
        assert _count_trades(clean_database) == 0

    def test_single_inconsistent_row_warns(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        bad = _mutate_row(lines[1], lines[0], ror="0.9999")  # pnl/risk is 0.6047
        f = tmp_path / "inconsistent.csv"
        f.write_text("\n".join([lines[0], lines[2], bad]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.ok
        assert result.rows_accepted == 2
        assert any("inconsistent with pnl/risk" in m for w in result.warnings for m in w.messages)

    def test_percent_symbol_cells_are_normalized(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        row = _mutate_row(lines[1], lines[0], ror="60.47%", returnPct="60.47%")
        f = tmp_path / "mixedsymbols.csv"
        f.write_text("\n".join([lines[0], row]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.ok and result.rows_accepted == 1
        engine = create_engine(clean_database)
        try:
            with engine.connect() as conn:
                stored = conn.execute(select(TradeRow.return_fraction)).scalar_one()
        finally:
            engine.dispose()
        assert float(stored) == pytest.approx(0.6047)


class TestDateOrderPolicy:
    """M4: ambiguous dates follow the configured order; contradictions reject."""

    def test_day_first_evidence_rejects_mdy_file(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        bad = _mutate_row(lines[1], lines[0], openDate="13/05/26 09:35")
        f = tmp_path / "dmyevidence.csv"
        f.write_text("\n".join([lines[0], bad]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert not result.ok
        assert result.error is not None and "date-order conflict" in result.error
        assert _count_trades(clean_database) == 0

    def test_explicit_dmy_option(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        row = _mutate_row(
            lines[1],
            lines[0],
            openDate="13/01/26 09:35",
            closeDate="13/01/26 14:12",
            expiration="13/01/26",
            highReturnPctDate="13/01/26 12:45",
            lowReturnPctDate="13/01/26 10:05",
        )
        f = tmp_path / "dmy.csv"
        f.write_text("\n".join([lines[0], row]) + "\n")
        result = OptionAlphaImporter(clean_database, date_order="DMY").import_files([f]).files[0]
        assert result.ok, result.error
        assert result.rows_accepted == 1
        engine = create_engine(clean_database)
        try:
            with engine.connect() as conn:
                opened = conn.execute(select(TradeRow.opened_at)).scalar_one()
        finally:
            engine.dispose()
        assert (opened.year, opened.month, opened.day) == (2026, 1, 13)

    def test_mdy_evidence_rejects_dmy_import(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        bad = _mutate_row(lines[1], lines[0], openDate="05/13/26 09:35")
        f = tmp_path / "mdyevidence.csv"
        f.write_text("\n".join([lines[0], bad]) + "\n")
        result = OptionAlphaImporter(clean_database, date_order="DMY").import_files([f]).files[0]
        assert not result.ok
        assert result.error is not None and "date-order conflict" in result.error

    def test_iso_dates_always_accepted(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        row = _mutate_row(
            lines[1],
            lines[0],
            openDate="2026-01-05 09:35",
            closeDate="2026-01-05T14:12:00",
            expiration="2026-01-05",
        )
        f = tmp_path / "iso.csv"
        f.write_text("\n".join([lines[0], row]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.ok and result.rows_accepted == 1


class TestEncodings:
    """M6: BOM-aware decoding; NUL bytes reject the file, not the rows."""

    def _sample_bytes(self, encoding: str) -> bytes:
        return (FIXTURES / "option_alpha_sample.csv").read_text().encode(encoding)

    @pytest.mark.parametrize(
        "encoding",
        ["utf-8", "utf-8-sig", "utf-16-le", "utf-16-be", "utf-16", "utf-32"],
    )
    def test_supported_encodings_import_fully(
        self, clean_database: str, tmp_path: Path, encoding: str
    ) -> None:
        data = self._sample_bytes(encoding)
        if encoding in ("utf-16-le", "utf-16-be"):
            # BOM-less wide encodings are unsupported -> clean file-level
            # rejection (NUL detection), never row noise.
            f = tmp_path / "nobom.csv"
            f.write_bytes(data)
            result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
            assert not result.ok
            assert result.error is not None and "NUL bytes" in result.error
            assert result.rows_received == 0
            return
        f = tmp_path / f"enc-{encoding}.csv"
        f.write_bytes(data)
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.ok, result.error
        assert result.rows_received == 12
        assert result.rows_accepted == 12

    def test_latin1_fallback_supported(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        row = _mutate_row(lines[1], lines[0], botName="Hulk Café 0DTE 0.50Δ 3x [Live]")
        data = ("\n".join([lines[0], row]) + "\n").encode("latin-1", errors="replace")
        f = tmp_path / "latin1.csv"
        f.write_bytes(data)
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.ok
        assert result.rows_accepted == 1

    def test_nul_bytes_without_bom_rejected(self, clean_database: str, tmp_path: Path) -> None:
        f = tmp_path / "nuls.csv"
        f.write_bytes(b"botName,symbol\x00,quantity\nX,SPY\x00,1\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert not result.ok
        assert result.error is not None and "NUL bytes" in result.error

    def test_quoted_multiline_fields(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        row = _mutate_row(lines[1], lines[0], description="SPY Iron Butterfly\nsecond line")
        f = tmp_path / "multiline.csv"
        f.write_text("\n".join([lines[0], row]) + "\n")
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.ok
        assert result.rows_accepted == 1
        engine = create_engine(clean_database)
        try:
            with engine.connect() as conn:
                desc = conn.execute(select(TradeRow.contract_description)).scalar_one()
        finally:
            engine.dispose()
        assert "second line" in desc
