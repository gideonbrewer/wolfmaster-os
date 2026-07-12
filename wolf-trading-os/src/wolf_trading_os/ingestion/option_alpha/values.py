"""Field-specific scalar parsers for Option Alpha CSV values.

Design rules (audit remediation H3/M3/M4):

- Parsers are FIELD-SPECIFIC. There is no generic "strip every symbol"
  parser: money fields tolerate ``$``/thousands separators/accounting
  negatives, quantities tolerate nothing but a sign, and return fields
  have explicit unit semantics.
- Return semantics: the canonical internal representation is a DECIMAL
  FRACTION (0.125 == 12.5%). A trailing ``%`` divides by 100
  ("12.5%" -> 0.125); a bare number is taken as a fraction as exported
  by Option Alpha. File-level unit-convention validation lives in the
  importer.
- Non-finite values (NaN/Infinity) are rejected, and every numeric field
  is range-checked against the actual database precision before insert.
- All parsers return None for empty / placeholder values ("", "--",
  "N/A", "null") and raise ValueError for values that are present but
  malformed, so callers can distinguish "absent" from "corrupt".
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

_EMPTY_TOKENS = {"", "-", "--", "n/a", "na", "none", "null", "nan"}

DateOrder = Literal["MDY", "DMY"]

# --------------------------------------------------------------------------
# strings / tags


def is_empty(raw: str | None) -> bool:
    return raw is None or raw.strip().lower() in _EMPTY_TOKENS


def clean_str(raw: str | None) -> str | None:
    """Trimmed string, or None if empty/placeholder."""
    if is_empty(raw):
        return None
    assert raw is not None
    return raw.strip()


def parse_tags(raw: str | None) -> tuple[str, ...]:
    """Split a tags cell on commas / semicolons / pipes."""
    text = clean_str(raw)
    if text is None:
        return ()
    parts = (p.strip() for p in re.split(r"[,;|]", text))
    return tuple(p for p in parts if p)


# --------------------------------------------------------------------------
# numbers

_MONEY_JUNK = re.compile(r"[$,\s]")
_PLAIN_NUMBER = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def _to_decimal(text: str, original: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {original!r}") from exc
    if not value.is_finite():
        raise ValueError(f"not a finite number: {original!r}")
    return value


def parse_money(raw: str | None) -> Decimal | None:
    """Money/price cell: tolerates "$1,234.50" and accounting negatives
    "(45.00)". Does NOT accept percent signs."""
    if is_empty(raw):
        return None
    assert raw is not None
    text = raw.strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = _MONEY_JUNK.sub("", text)
    if text.lower() in _EMPTY_TOKENS:
        return None
    value = _to_decimal(text, raw)
    return -value if negative else value


def parse_quantity(raw: str | None) -> Decimal | None:
    """Quantity cell: a plain signed number only — no $, %, separators."""
    if is_empty(raw):
        return None
    assert raw is not None
    text = raw.strip()
    if not _PLAIN_NUMBER.match(text):
        raise ValueError(f"not a plain number: {raw!r}")
    return _to_decimal(text, raw)


def parse_return(raw: str | None) -> Decimal | None:
    """Return/excursion cell -> canonical DECIMAL FRACTION.

    "0.125"  -> Decimal("0.125")   (12.5%, Option Alpha convention)
    "12.5%"  -> Decimal("0.125")
    "-3.8835%" -> Decimal("-0.038835")
    """
    if is_empty(raw):
        return None
    assert raw is not None
    text = raw.strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    if not _PLAIN_NUMBER.match(text):
        raise ValueError(f"not a number: {raw!r}")
    value = _to_decimal(text, raw)
    if negative:
        value = -value
    return value / 100 if percent else value


def parse_int(raw: str | None) -> int | None:
    """Integer cell; rejects non-integral values."""
    value = parse_quantity(raw)
    if value is None:
        return None
    if value != value.to_integral_value():
        raise ValueError(f"not an integer: {raw!r}")
    return int(value)


# --------------------------------------------------------------------------
# range validation against actual database precision (see orm.py)

# field -> (max exclusive absolute value, minimum allowed value or None)
NUMERIC_LIMITS: dict[str, tuple[Decimal, Decimal | None]] = {
    "quantity": (Decimal("1e12"), Decimal("0")),  # NUMERIC(20,8); must be > 0
    "days_in_trade": (Decimal("1e8"), Decimal("0")),  # NUMERIC(12,4)
    "entry_price": (Decimal("1e12"), None),  # NUMERIC(20,8)
    "exit_price": (Decimal("1e12"), None),
    "premium": (Decimal("1e16"), None),  # NUMERIC(20,4); sign is valid (debit/credit)
    "risk": (Decimal("1e16"), Decimal("0")),  # capital at risk is non-negative
    "realized_pnl": (Decimal("1e16"), None),
    "return_fraction": (Decimal("1e6"), None),  # NUMERIC(14,8)
    "return_on_risk": (Decimal("1e6"), None),
    "mfe_fraction": (Decimal("1e6"), None),
    "mae_fraction": (Decimal("1e6"), None),
    "underlying_entry_price": (Decimal("1e12"), None),
    "underlying_exit_price": (Decimal("1e12"), None),
}


def check_range(field: str, value: Decimal | None) -> Decimal | None:
    """Validate a parsed value against the database column limits.

    Raises ValueError naming the field and value when out of range, so
    the row (not the file) is rejected before any database round trip.
    """
    if value is None:
        return None
    max_abs, minimum = NUMERIC_LIMITS[field]
    if abs(value) >= max_abs:
        raise ValueError(f"{field}: value {value} out of range (|x| < {max_abs:.0e})")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field}: value {value} below minimum {minimum}")
    return value


# --------------------------------------------------------------------------
# timestamps

TZ_UNKNOWN = "tz_unknown"
TZ_EXPLICIT_OFFSET = "explicit_offset"


@dataclass(frozen=True, slots=True)
class ParsedTimestamp:
    """A parsed timestamp with provenance.

    ``local`` is the wall-clock time exactly as written in the source.
    ``utc`` is populated ONLY when the source carried an explicit UTC
    offset — a timezone is never guessed (AGENTS.md rule 4).
    """

    local: dt.datetime  # naive wall clock as written
    utc: dt.datetime | None  # aware UTC instant, only if offset was explicit
    confidence: str  # TZ_UNKNOWN | TZ_EXPLICIT_OFFSET


# Unambiguous formats, always accepted.
_ISO_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)

# Slash formats are AMBIGUOUS (02/03/26): they are only parsed under an
# explicit, file-level date order. MDY is the confirmed Option Alpha
# export convention and the default; contradictory evidence rejects the
# whole file (see importer.scan_date_order_conflicts).
_SLASH_FORMATS: dict[DateOrder, tuple[str, ...]] = {
    "MDY": (
        "%m/%d/%y %H:%M",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %I:%M %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%y %I:%M:%S %p",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%y",
        "%m/%d/%Y",
    ),
    "DMY": (
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%y %I:%M %p",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%y %I:%M:%S %p",
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%y",
        "%d/%m/%Y",
    ),
}

_TZ_ABBREV = re.compile(r"\s+(?:ET|EST|EDT)$", re.IGNORECASE)
_HAS_SLASH_DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")


def parse_timestamp(raw: str | None, date_order: DateOrder = "MDY") -> ParsedTimestamp | None:
    """Parse a timestamp cell.

    ISO-8601 is preferred (with or without an explicit UTC offset).
    Slash dates are parsed under the given ``date_order`` only.
    """
    if is_empty(raw):
        return None
    assert raw is not None
    text = raw.strip()
    # Strip a trailing timezone abbreviation Option Alpha sometimes appends;
    # it names a zone colloquially but is not a reliable offset, so the
    # timestamp still counts as tz-unknown.
    text = _TZ_ABBREV.sub("", text)

    # ISO first — including explicit offsets ("2026-01-05T09:35:00-05:00").
    try:
        iso = dt.datetime.fromisoformat(text)
    except ValueError:
        iso = None
    if iso is not None:
        if iso.tzinfo is not None:
            return ParsedTimestamp(
                local=iso.replace(tzinfo=None),
                utc=iso.astimezone(dt.UTC),
                confidence=TZ_EXPLICIT_OFFSET,
            )
        return ParsedTimestamp(local=iso, utc=None, confidence=TZ_UNKNOWN)

    for fmt in (*_ISO_FORMATS, *_SLASH_FORMATS[date_order]):
        try:
            parsed = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        return ParsedTimestamp(local=parsed, utc=None, confidence=TZ_UNKNOWN)
    raise ValueError(f"unrecognized timestamp: {raw!r}")


def slash_date_order_evidence(raw: str | None) -> DateOrder | None:
    """Which date order a slash-formatted cell PROVES, if any.

    Returns "MDY" when the value only parses month-first, "DMY" when it
    only parses day-first, and None when it is empty, non-slash, or
    valid under both orders (ambiguous).
    """
    if is_empty(raw):
        return None
    assert raw is not None
    text = _TZ_ABBREV.sub("", raw.strip())
    if not _HAS_SLASH_DATE.search(text):
        return None

    def parses(order: DateOrder) -> bool:
        for fmt in _SLASH_FORMATS[order]:
            try:
                dt.datetime.strptime(text, fmt)
                return True
            except ValueError:
                continue
        return False

    mdy, dmy = parses("MDY"), parses("DMY")
    if mdy and not dmy:
        return "MDY"
    if dmy and not mdy:
        return "DMY"
    return None
