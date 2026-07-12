"""Tolerant scalar parsers for Option Alpha CSV values.

All parsers return None for empty / placeholder values ("", "--", "N/A",
"null") and raise ValueError for values that are present but malformed,
so callers can distinguish "absent" from "corrupt".
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation

_EMPTY_TOKENS = {"", "-", "--", "n/a", "na", "none", "null", "nan"}

# Formats seen in Option Alpha exports and common spreadsheet round-trips.
_DATETIME_FORMATS = (
    "%m/%d/%y %H:%M",
    "%m/%d/%Y %H:%M",
    "%m/%d/%y %I:%M %p",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%y %I:%M:%S %p",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%y",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)

_NUMERIC_JUNK = re.compile(r"[$,%\s]")


def is_empty(raw: str | None) -> bool:
    return raw is None or raw.strip().lower() in _EMPTY_TOKENS


def clean_str(raw: str | None) -> str | None:
    """Trimmed string, or None if empty/placeholder."""
    if is_empty(raw):
        return None
    assert raw is not None
    return raw.strip()


def parse_decimal(raw: str | None) -> Decimal | None:
    """Parse a numeric cell.

    Tolerates currency symbols, thousands separators, percent signs, and
    accounting-style negatives: "$1,234.50", "(45.00)", "12.5%".
    """
    if is_empty(raw):
        return None
    assert raw is not None
    text = raw.strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = _NUMERIC_JUNK.sub("", text)
    if text.lower() in _EMPTY_TOKENS:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {raw!r}") from exc
    return -value if negative else value


def parse_int(raw: str | None) -> int | None:
    """Parse an integer cell; rejects non-integral values."""
    value = parse_decimal(raw)
    if value is None:
        return None
    if value != value.to_integral_value():
        raise ValueError(f"not an integer: {raw!r}")
    return int(value)


def parse_timestamp(raw: str | None) -> dt.datetime | None:
    """Parse a timestamp cell to a naive datetime (exchange-local wall clock).

    Option Alpha exports carry no timezone information; values are stored
    exactly as exported.
    """
    if is_empty(raw):
        return None
    assert raw is not None
    text = raw.strip()
    # Strip a trailing timezone abbreviation Option Alpha sometimes appends.
    text = re.sub(r"\s+(?:ET|EST|EDT)$", "", text, flags=re.IGNORECASE)
    for fmt in _DATETIME_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognized timestamp: {raw!r}")


def parse_tags(raw: str | None) -> tuple[str, ...]:
    """Split a tags cell on commas / semicolons / pipes."""
    text = clean_str(raw)
    if text is None:
        return ()
    parts = (p.strip() for p in re.split(r"[,;|]", text))
    return tuple(p for p in parts if p)
