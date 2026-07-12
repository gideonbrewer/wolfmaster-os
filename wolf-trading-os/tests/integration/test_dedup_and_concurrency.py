"""Fingerprint v2 dedup semantics and concurrent-import safety (H1/M1/H4)."""

from __future__ import annotations

import csv
import io
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text, update

from wolf_trading_os.database.orm import ImportBatchRow, TradeRow
from wolf_trading_os.ingestion.option_alpha import ImportSummary, OptionAlphaImporter

FIXTURES = Path(__file__).parents[1] / "fixtures"

pytestmark = pytest.mark.integration


def _count_trades(db_url: str) -> int:
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(TradeRow)).scalar_one())
    finally:
        engine.dispose()


def _count_batches(db_url: str) -> int:
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(ImportBatchRow)).scalar_one())
    finally:
        engine.dispose()


def _sample_lines() -> list[str]:
    return (FIXTURES / "option_alpha_sample.csv").read_text().splitlines()


def _write_csv(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n")
    return path


def _mutate_row(line: str, header: str, **overrides: str) -> str:
    columns = header.split(",")
    cells = next(csv.reader(io.StringIO(line)))
    for column, value in overrides.items():
        cells[columns.index(column)] = value
    buf = io.StringIO()
    csv.writer(buf).writerow(cells)
    return buf.getvalue().strip("\r\n")


class TestOccurrenceSemantics:
    def test_same_row_two_separate_imports_one_stored(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        f = _write_csv(tmp_path / "one.csv", [lines[0], lines[1]])
        importer = OptionAlphaImporter(clean_database)
        importer.import_files([f])
        summary = importer.import_files([f])
        assert summary.rows_duplicate == 1
        assert _count_trades(clean_database) == 1

    def test_two_identical_rows_in_one_file_both_stored(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        f = _write_csv(tmp_path / "twins.csv", [lines[0], lines[1], lines[1]])
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.rows_accepted == 2
        assert result.rows_duplicate == 0
        assert any("repeated identical source rows" in w for w in result.file_warnings)
        assert _count_trades(clean_database) == 2

    def test_reimport_twins_file_all_duplicates(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        f = _write_csv(tmp_path / "twins.csv", [lines[0], lines[1], lines[1]])
        importer = OptionAlphaImporter(clean_database)
        importer.import_files([f])
        summary = importer.import_files([f])
        assert summary.rows_accepted == 0
        assert summary.rows_duplicate == 2
        assert _count_trades(clean_database) == 2

    def test_same_visible_trade_from_two_bots_both_stored(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        other = _mutate_row(lines[1], lines[0], botName="Banshee 0DTE 0.50Δ 3x [Live]")
        f = _write_csv(tmp_path / "bots.csv", [lines[0], lines[1], other])
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.rows_accepted == 2
        assert _count_trades(clean_database) == 2

    def test_live_and_paper_tag_rows_both_stored(self, clean_database: str, tmp_path: Path) -> None:
        lines = _sample_lines()
        live = _mutate_row(lines[1], lines[0], tags="live")
        paper = _mutate_row(lines[1], lines[0], tags="paper")
        f = _write_csv(tmp_path / "envs.csv", [lines[0], live, paper])
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.rows_accepted == 2
        assert _count_trades(clean_database) == 2

    def test_equivalent_numeric_formatting_deduplicates(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        # quantity "3" -> "3.0", pnl "390.00" -> "$390"
        reformatted = _mutate_row(lines[1], lines[0], quantity="3.0", pnl="$390")
        importer = OptionAlphaImporter(clean_database)
        importer.import_files([_write_csv(tmp_path / "a.csv", [lines[0], lines[1]])])
        summary = importer.import_files([_write_csv(tmp_path / "b.csv", [lines[0], reformatted])])
        assert summary.rows_duplicate == 1
        assert _count_trades(clean_database) == 1


class TestLegacyOa1Dedup:
    def test_rows_imported_before_migration_still_deduplicate(self, clean_database: str) -> None:
        importer = OptionAlphaImporter(clean_database)
        importer.import_files([FIXTURES / "option_alpha_sample.csv"])
        # Simulate a pre-oa2 database: rewrite stored rows to legacy form.
        from wolf_trading_os.ingestion.option_alpha.fingerprint import compute_fingerprint_v1

        engine = create_engine(clean_database)
        try:
            with engine.begin() as conn:
                rows = conn.execute(select(TradeRow.trade_id, TradeRow.raw_payload)).all()
                for trade_id, payload in rows:
                    conn.execute(
                        update(TradeRow)
                        .where(TradeRow.trade_id == trade_id)
                        .values(
                            fingerprint=compute_fingerprint_v1(payload),
                            fingerprint_version="oa1",
                        )
                    )
        finally:
            engine.dispose()

        summary = importer.import_files([FIXTURES / "option_alpha_sample.csv"])
        assert summary.rows_accepted == 0
        assert summary.rows_duplicate == 12
        assert _count_trades(clean_database) == 12


class TestConcurrency:
    def _run_concurrent(
        self, db_url: str, files_per_thread: list[list[Path]]
    ) -> list[ImportSummary | Exception]:
        results: list[ImportSummary | Exception] = [None] * len(files_per_thread)  # type: ignore[list-item]

        def worker(i: int, files: list[Path]) -> None:
            try:
                results[i] = OptionAlphaImporter(db_url).import_files(files)
            except Exception as exc:  # pragma: no cover - the assertion target
                results[i] = exc

        threads = [
            threading.Thread(target=worker, args=(i, files))
            for i, files in enumerate(files_per_thread)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    def test_two_concurrent_imports_of_same_file(self, clean_database: str) -> None:
        sample = FIXTURES / "option_alpha_sample.csv"
        results = self._run_concurrent(clean_database, [[sample], [sample]])
        assert all(isinstance(r, ImportSummary) for r in results), results
        summaries = [r for r in results if isinstance(r, ImportSummary)]
        assert sum(s.rows_accepted for s in summaries) == 12
        assert sum(s.rows_duplicate for s in summaries) == 12
        assert _count_trades(clean_database) == 12
        assert _count_batches(clean_database) == 2  # both audit records persisted

    def test_three_concurrent_imports(self, clean_database: str) -> None:
        sample = FIXTURES / "option_alpha_sample.csv"
        results = self._run_concurrent(clean_database, [[sample]] * 3)
        assert all(isinstance(r, ImportSummary) for r in results), results
        summaries = [r for r in results if isinstance(r, ImportSummary)]
        assert sum(s.rows_accepted for s in summaries) == 12
        assert sum(s.rows_duplicate for s in summaries) == 24
        assert _count_trades(clean_database) == 12
        assert _count_batches(clean_database) == 3

    def test_concurrent_overlapping_files(self, clean_database: str) -> None:
        results = self._run_concurrent(
            clean_database,
            [[FIXTURES / "option_alpha_sample.csv"], [FIXTURES / "option_alpha_overlap.csv"]],
        )
        assert all(isinstance(r, ImportSummary) for r in results), results
        # sample=12 rows, overlap=4 rows sharing 2 -> 14 distinct trades.
        assert _count_trades(clean_database) == 14

    def test_concurrent_import_with_malformed_rows(self, clean_database: str) -> None:
        malformed = FIXTURES / "option_alpha_malformed.csv"
        results = self._run_concurrent(clean_database, [[malformed], [malformed]])
        assert all(isinstance(r, ImportSummary) for r in results), results
        summaries = [r for r in results if isinstance(r, ImportSummary)]
        assert all(s.files[0].rows_rejected == 4 for s in summaries)
        assert _count_trades(clean_database) == 2

    def test_duplicate_containing_file_concurrent(
        self, clean_database: str, tmp_path: Path
    ) -> None:
        lines = _sample_lines()
        f = _write_csv(tmp_path / "twins.csv", [lines[0], lines[1], lines[1]])
        results = self._run_concurrent(clean_database, [[f], [f]])
        assert all(isinstance(r, ImportSummary) for r in results), results
        summaries = [r for r in results if isinstance(r, ImportSummary)]
        assert sum(s.rows_accepted for s in summaries) == 2  # no missing trades
        assert _count_trades(clean_database) == 2


class TestInterruptedImportRetry:
    def test_retry_after_interrupted_transaction(
        self, clean_database: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        importer = OptionAlphaImporter(clean_database)

        import wolf_trading_os.ingestion.option_alpha.importer as importer_module

        original = importer_module.finalize_import_batch

        def explode(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated interruption")

        monkeypatch.setattr(importer_module, "finalize_import_batch", explode)
        with pytest.raises(RuntimeError, match="simulated interruption"):
            importer.import_files([FIXTURES / "option_alpha_sample.csv"])
        # Atomic rollback: nothing persisted, not even the audit batch.
        assert _count_trades(clean_database) == 0
        assert _count_batches(clean_database) == 0

        monkeypatch.setattr(importer_module, "finalize_import_batch", original)
        summary = importer.import_files([FIXTURES / "option_alpha_sample.csv"])
        assert summary.rows_accepted == 12
        assert _count_trades(clean_database) == 12

    def test_fingerprint_version_stored(self, clean_database: str) -> None:
        OptionAlphaImporter(clean_database).import_files([FIXTURES / "option_alpha_sample.csv"])
        engine = create_engine(clean_database)
        try:
            with engine.connect() as conn:
                versions = set(
                    conn.execute(text("SELECT DISTINCT fingerprint_version FROM trades"))
                    .scalars()
                    .all()
                )
        finally:
            engine.dispose()
        assert versions == {"oa2"}
