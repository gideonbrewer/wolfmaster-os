"""Timestamp provenance (M9) and database constraints (item 12)."""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert, inspect, select
from sqlalchemy.exc import IntegrityError

from wolf_trading_os.database.orm import TradeRow
from wolf_trading_os.ingestion.option_alpha import OptionAlphaImporter
from wolf_trading_os.ingestion.option_alpha.values import parse_timestamp

FIXTURES = Path(__file__).parents[1] / "fixtures"

pytestmark = pytest.mark.integration


def _sample_lines() -> list[str]:
    return (FIXTURES / "option_alpha_sample.csv").read_text().splitlines()


class TestTimestampProvenance:
    def test_oa_rows_stay_timezone_unknown(self, clean_database: str) -> None:
        """No timezone is guessed or backfilled for Option Alpha rows."""
        OptionAlphaImporter(clean_database).import_files([FIXTURES / "option_alpha_sample.csv"])
        engine = create_engine(clean_database)
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    select(
                        TradeRow.opened_at,
                        TradeRow.opened_at_utc,
                        TradeRow.source_timezone,
                        TradeRow.timestamp_confidence,
                        TradeRow.exchange_timezone,
                        TradeRow.asset_class,
                    )
                ).all()
        finally:
            engine.dispose()
        assert rows
        for opened_at, opened_utc, source_tz, confidence, exchange_tz, asset_class in rows:
            assert opened_at is not None and opened_at.tzinfo is None  # wall clock
            assert opened_utc is None  # never derived without an explicit offset
            assert source_tz is None  # explicitly timezone-unknown
            assert confidence == "tz_unknown"
            if asset_class in ("equity", "equity_option"):
                assert exchange_tz == "America/New_York"  # venue knowledge
            else:
                assert exchange_tz is None

    def test_explicit_offset_populates_utc(self, clean_database: str, tmp_path: Path) -> None:
        import csv
        import io

        lines = _sample_lines()
        header = lines[0]
        cells = next(csv.reader(io.StringIO(lines[1])))
        columns = header.split(",")
        cells[columns.index("openDate")] = "2026-01-05T09:35:00-05:00"
        cells[columns.index("closeDate")] = "2026-01-05T14:12:00-05:00"
        buf = io.StringIO()
        csv.writer(buf).writerow(cells)
        f = tmp_path / "offsets.csv"
        f.write_text(header + "\n" + buf.getvalue())
        result = OptionAlphaImporter(clean_database).import_files([f]).files[0]
        assert result.rows_accepted == 1

        engine = create_engine(clean_database)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    select(
                        TradeRow.opened_at,
                        TradeRow.opened_at_utc,
                        TradeRow.timestamp_confidence,
                    )
                ).one()
        finally:
            engine.dispose()
        assert row.opened_at == dt.datetime(2026, 1, 5, 9, 35)  # local wall clock
        assert row.opened_at_utc == dt.datetime(2026, 1, 5, 14, 35, tzinfo=dt.UTC)
        assert row.timestamp_confidence == "explicit_offset"


class TestDstBehavior:
    def test_ambiguous_dst_wall_clock_stored_verbatim(self) -> None:
        # 2026-11-01 01:30 occurs twice in US/Eastern (fall-back). With no
        # offset the value is stored verbatim as wall clock and stays
        # timezone-unknown — never disambiguated by guessing.
        parsed = parse_timestamp("11/01/26 01:30")
        assert parsed is not None
        assert parsed.local == dt.datetime(2026, 11, 1, 1, 30)
        assert parsed.utc is None
        assert parsed.confidence == "tz_unknown"


class TestDatabaseConstraints:
    def _base_row(self) -> dict[str, object]:
        return {
            "trade_id": uuid.uuid4(),
            "fingerprint": uuid.uuid4().hex + uuid.uuid4().hex,
            "fingerprint_version": "oa2",
            "source": "option_alpha",
            "underlying_symbol": "SPY",
            "environment": "unknown",
            "asset_class": "unknown",
            "instrument_type": "unknown",
            "direction": "unknown",
            "status": "unknown",
            "timestamp_confidence": "tz_unknown",
            "parse_sources": {},
            "tags": [],
            "raw_payload": {},
        }

    @pytest.mark.parametrize(
        ("override", "constraint"),
        [
            ({"quantity": -1}, "ck_trades_quantity_positive"),
            ({"quantity": 0}, "ck_trades_quantity_positive"),
            ({"fingerprint": ""}, "ck_trades_fingerprint_not_empty"),
            ({"fingerprint_version": "bogus"}, "ck_trades_fingerprint_version_valid"),
            ({"source": "robinhood"}, "ck_trades_source_valid"),
            ({"timestamp_confidence": "guessed"}, "ck_trades_timestamp_confidence_valid"),
        ],
    )
    def test_check_constraints_enforced(
        self, clean_database: str, override: dict[str, object], constraint: str
    ) -> None:
        engine = create_engine(clean_database)
        try:
            with pytest.raises(IntegrityError, match=constraint), engine.begin() as conn:
                conn.execute(insert(TradeRow).values({**self._base_row(), **override}))
        finally:
            engine.dispose()

    def test_valid_row_passes_constraints(self, clean_database: str) -> None:
        engine = create_engine(clean_database)
        try:
            with engine.begin() as conn:
                conn.execute(insert(TradeRow).values({**self._base_row(), "quantity": 1}))
        finally:
            engine.dispose()

    def test_constraints_present_in_schema(self, scratch_database_url: str) -> None:
        engine = create_engine(scratch_database_url)
        try:
            checks = {c["name"] for c in inspect(engine).get_check_constraints("trades")}
        finally:
            engine.dispose()
        assert {
            "ck_trades_quantity_positive",
            "ck_trades_fingerprint_not_empty",
            "ck_trades_fingerprint_version_valid",
            "ck_trades_source_valid",
            "ck_trades_timestamp_confidence_valid",
        } <= checks
