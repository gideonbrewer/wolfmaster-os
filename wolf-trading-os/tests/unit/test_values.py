"""Numeric, timestamp, null, and tag parsing."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wolf_trading_os.ingestion.option_alpha import values


class TestParseDecimal:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1.5", Decimal("1.5")),
            ("-270.00", Decimal("-270.00")),
            ("$1,234.50", Decimal("1234.50")),
            ("(45.00)", Decimal("-45.00")),
            ("12.5%", Decimal("12.5")),
            (" 3 ", Decimal("3")),
            ("0", Decimal("0")),
        ],
    )
    def test_valid(self, raw: str, expected: Decimal) -> None:
        assert values.parse_decimal(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "  ", "--", "N/A", "null", "NaN", "none"])
    def test_null_like_returns_none(self, raw: str | None) -> None:
        assert values.parse_decimal(raw) is None

    @pytest.mark.parametrize("raw", ["abc", "12.3.4", "1O0"])
    def test_malformed_raises(self, raw: str) -> None:
        with pytest.raises(ValueError, match="not a number"):
            values.parse_decimal(raw)


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
    def test_valid(self, raw: str, expected: dt.datetime) -> None:
        assert values.parse_timestamp(raw) == expected

    def test_empty_is_none(self) -> None:
        assert values.parse_timestamp("") is None
        assert values.parse_timestamp(None) is None

    @pytest.mark.parametrize("raw", ["banana", "13/45/26", "2026-99-01"])
    def test_invalid_raises(self, raw: str) -> None:
        with pytest.raises(ValueError, match="unrecognized timestamp"):
            values.parse_timestamp(raw)

    def test_result_is_naive(self) -> None:
        parsed = values.parse_timestamp("01/05/26 09:35")
        assert parsed is not None and parsed.tzinfo is None


class TestParseTags:
    def test_split_variants(self) -> None:
        assert values.parse_tags("a, b;c |d") == ("a", "b", "c", "d")

    def test_empty(self) -> None:
        assert values.parse_tags(None) == ()
        assert values.parse_tags("  ") == ()
