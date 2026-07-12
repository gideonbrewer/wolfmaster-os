"""Field-specific numeric, return, timestamp, and range parsing."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wolf_trading_os.ingestion.option_alpha import values


class TestParseMoney:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1.5", Decimal("1.5")),
            ("-270.00", Decimal("-270.00")),
            ("$1,234.50", Decimal("1234.50")),
            ("(45.00)", Decimal("-45.00")),
            (" 3 ", Decimal("3")),
            ("0", Decimal("0")),
        ],
    )
    def test_valid(self, raw: str, expected: Decimal) -> None:
        assert values.parse_money(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "  ", "--", "N/A", "null", "NaN", "none"])
    def test_null_like_returns_none(self, raw: str | None) -> None:
        assert values.parse_money(raw) is None

    @pytest.mark.parametrize("raw", ["abc", "12.3.4", "1O0", "12.5%"])
    def test_malformed_raises(self, raw: str) -> None:
        with pytest.raises(ValueError, match="not a"):
            values.parse_money(raw)

    @pytest.mark.parametrize("raw", ["Infinity", "-Infinity", "inf"])
    def test_non_finite_rejected(self, raw: str) -> None:
        with pytest.raises(ValueError, match=r"not a (finite )?number"):
            values.parse_money(raw)


class TestParseQuantity:
    def test_plain_numbers_only(self) -> None:
        assert values.parse_quantity("3") == Decimal("3")
        assert values.parse_quantity("2.5") == Decimal("2.5")
        assert values.parse_quantity("-1") == Decimal("-1")

    @pytest.mark.parametrize("raw", ["$3", "3%", "1,000", "(3)"])
    def test_symbols_rejected(self, raw: str) -> None:
        with pytest.raises(ValueError, match="not a plain number"):
            values.parse_quantity(raw)

    def test_empty_is_none(self) -> None:
        assert values.parse_quantity("") is None


class TestParseReturn:
    """Canonical representation: DECIMAL FRACTION (0.125 == 12.5%)."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0.125", Decimal("0.125")),
            ("12.5%", Decimal("0.125")),
            ("-3.8835%", Decimal("-0.038835")),
            ("-0.038835", Decimal("-0.038835")),
            ("0.32291667", Decimal("0.32291667")),
            ("1", Decimal("1")),  # +100%
            ("100%", Decimal("1")),
            ("(12.5%)", Decimal("-0.125")),
        ],
    )
    def test_units(self, raw: str, expected: Decimal) -> None:
        assert values.parse_return(raw) == expected

    def test_bare_percent_points_are_not_reinterpreted(self) -> None:
        # "12.5" without a % sign is taken as a fraction (1250%) — the
        # file-level unit-convention check catches misformatted exports;
        # no silent 100x adjustment happens here.
        assert values.parse_return("12.5") == Decimal("12.5")

    def test_empty_is_none(self) -> None:
        assert values.parse_return(None) is None
        assert values.parse_return("--") is None

    @pytest.mark.parametrize("raw", ["abc", "%", "12..5%", "NaN%"])
    def test_malformed_raises(self, raw: str) -> None:
        with pytest.raises(ValueError):
            values.parse_return(raw)


class TestCheckRange:
    def test_within_range_passes_through(self) -> None:
        assert values.check_range("realized_pnl", Decimal("390")) == Decimal("390")
        assert values.check_range("realized_pnl", None) is None

    def test_overflow_rejected_with_field_and_value(self) -> None:
        with pytest.raises(ValueError, match=r"realized_pnl.*99999999999999999999999"):
            values.check_range("realized_pnl", Decimal("99999999999999999999999"))

    def test_negative_risk_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"risk.*below minimum"):
            values.check_range("risk", Decimal("-100"))

    def test_huge_underlying_price_rejected(self) -> None:
        with pytest.raises(ValueError, match="underlying_entry_price"):
            values.check_range("underlying_entry_price", Decimal("1e13"))

    def test_return_fraction_bounds(self) -> None:
        assert values.check_range("return_fraction", Decimal("1.5")) == Decimal("1.5")
        with pytest.raises(ValueError, match="return_fraction"):
            values.check_range("return_fraction", Decimal("1e7"))


class TestParseInt:
    def test_valid(self) -> None:
        assert values.parse_int("3") == 3

    def test_non_integral_raises(self) -> None:
        with pytest.raises(ValueError, match="not an integer"):
            values.parse_int("3.5")

    def test_empty_is_none(self) -> None:
        assert values.parse_int("") is None


class TestParseTimestamp:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("01/05/26 09:35", dt.datetime(2026, 1, 5, 9, 35)),
            ("01/05/2026 09:35", dt.datetime(2026, 1, 5, 9, 35)),
            ("1/5/26 2:45 PM", dt.datetime(2026, 1, 5, 14, 45)),
            ("01/05/26", dt.datetime(2026, 1, 5)),
            ("2026-01-05 09:35:00", dt.datetime(2026, 1, 5, 9, 35)),
            ("2026-01-05T09:35:00", dt.datetime(2026, 1, 5, 9, 35)),
            ("2026-01-05", dt.datetime(2026, 1, 5)),
            ("01/05/26 09:35 ET", dt.datetime(2026, 1, 5, 9, 35)),
        ],
    )
    def test_local_wall_clock(self, raw: str, expected: dt.datetime) -> None:
        parsed = values.parse_timestamp(raw)
        assert parsed is not None
        assert parsed.local == expected
        assert parsed.local.tzinfo is None

    def test_no_offset_is_tz_unknown(self) -> None:
        parsed = values.parse_timestamp("01/05/26 09:35")
        assert parsed is not None
        assert parsed.utc is None
        assert parsed.confidence == values.TZ_UNKNOWN

    def test_explicit_offset_yields_utc(self) -> None:
        parsed = values.parse_timestamp("2026-01-05T09:35:00-05:00")
        assert parsed is not None
        assert parsed.local == dt.datetime(2026, 1, 5, 9, 35)
        assert parsed.utc == dt.datetime(2026, 1, 5, 14, 35, tzinfo=dt.UTC)
        assert parsed.confidence == values.TZ_EXPLICIT_OFFSET

    def test_same_wall_clock_different_offsets_differ_in_utc(self) -> None:
        east = values.parse_timestamp("2026-01-05T09:35:00-05:00")
        west = values.parse_timestamp("2026-01-05T09:35:00-08:00")
        assert east is not None and west is not None
        assert east.local == west.local
        assert east.utc != west.utc

    def test_day_first_order(self) -> None:
        parsed = values.parse_timestamp("31/01/26 09:35", date_order="DMY")
        assert parsed is not None
        assert parsed.local == dt.datetime(2026, 1, 31, 9, 35)

    def test_ambiguous_slash_date_follows_configured_order(self) -> None:
        mdy = values.parse_timestamp("02/03/26", date_order="MDY")
        dmy = values.parse_timestamp("02/03/26", date_order="DMY")
        assert mdy is not None and dmy is not None
        assert mdy.local == dt.datetime(2026, 2, 3)
        assert dmy.local == dt.datetime(2026, 3, 2)

    def test_empty_is_none(self) -> None:
        assert values.parse_timestamp("") is None
        assert values.parse_timestamp(None) is None

    @pytest.mark.parametrize("raw", ["banana", "13/45/26", "2026-99-01"])
    def test_invalid_raises(self, raw: str) -> None:
        with pytest.raises(ValueError, match="unrecognized timestamp"):
            values.parse_timestamp(raw)

    def test_day_first_only_value_rejected_under_mdy(self) -> None:
        with pytest.raises(ValueError, match="unrecognized timestamp"):
            values.parse_timestamp("13/05/26", date_order="MDY")


class TestSlashDateOrderEvidence:
    def test_proves_dmy(self) -> None:
        assert values.slash_date_order_evidence("13/05/26") == "DMY"

    def test_proves_mdy(self) -> None:
        assert values.slash_date_order_evidence("05/13/26") == "MDY"

    def test_ambiguous_is_none(self) -> None:
        assert values.slash_date_order_evidence("02/03/26") is None

    def test_iso_and_empty_are_none(self) -> None:
        assert values.slash_date_order_evidence("2026-01-05") is None
        assert values.slash_date_order_evidence("") is None


class TestParseTags:
    def test_split_variants(self) -> None:
        assert values.parse_tags("a, b;c |d") == ("a", "b", "c", "d")

    def test_empty(self) -> None:
        assert values.parse_tags(None) == ()
        assert values.parse_tags("  ") == ()
