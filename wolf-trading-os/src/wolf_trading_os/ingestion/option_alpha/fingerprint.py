"""Deterministic, versioned trade fingerprinting for duplicate detection.

Two algorithm versions exist. The version used for a stored row is
recorded in ``trades.fingerprint_version``.

``oa1`` (legacy — retained for migration/audit only)
    SHA-256 over 12 raw (whitespace-trimmed) fields. Weaknesses fixed by
    oa2: no source discriminator, no tags (paper/live tag-only rows
    collided), no occurrence index (repeated identical rows inside one
    file were silently dropped), and format-sensitive (``3`` vs ``3.0``
    hashed differently).

``oa2`` (current)
    SHA-256 over the normalized identity fields listed in
    ``FINGERPRINT_V2_FIELDS`` plus a deterministic per-file occurrence
    index. Included fields and why:

    - ``source``          data source discriminator ("option_alpha")
    - ``botName``         bot identity + raw environment markers
    - ``tags``            raw tags cell (may carry live/paper markers)
    - ``symbol``          underlying symbol
    - ``description``     contract description
    - ``expiration``      normalized timestamp
    - ``openDate``        normalized timestamp
    - ``closeDate``       normalized timestamp
    - ``quantity``        normalized numeric
    - ``openPrice``       normalized numeric (entry price)
    - ``closePrice``      normalized numeric (exit price)
    - ``pnl``             normalized numeric

    Deliberately EXCLUDED (documented per data-model.md): ``type``,
    ``status``, ``premium``, ``risk``, ``ror``, ``returnPct``, ``ev``,
    ``alpha``, ``highReturnPct``/``lowReturnPct`` (+dates),
    ``daysInTrade``, ``underlyingOpen``/``underlyingClose`` — these are
    derived/analytic values the platform may recompute or restate
    without the underlying trade being a different trade. Changes to
    them are handled by the possible-correction detector, not by
    creating a new identity.

    Normalization before hashing: strings are whitespace-trimmed;
    numeric fields are canonicalized through Decimal (``3`` == ``3.0``
    == `` 3.00``); timestamp fields are canonicalized to ISO-8601 when
    parseable. Unparseable values fall back to the trimmed raw text.
    Missing and empty are equivalent.

Occurrence index
    Rows inside a single file that share the same base oa2 identity are
    genuinely distinct trades (a platform does not export the same trade
    twice in one file). The k-th such row (in file order, 1-based) gets
    ``occ=k`` appended to the hashed material, so re-importing the same
    file reproduces identical fingerprints and deduplicates, while both
    original trades are preserved.

Changing either field list is a breaking change requiring a new version
string and a migration strategy (see docs/decisions.md ADR-016).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

FINGERPRINT_V1_FIELDS: tuple[str, ...] = (
    "botName",
    "type",
    "description",
    "symbol",
    "quantity",
    "openDate",
    "closeDate",
    "expiration",
    "openPrice",
    "closePrice",
    "premium",
    "pnl",
)

# (column, normalization) pairs for oa2. "source" is injected, not a column.
_V2_TEXT_FIELDS: tuple[str, ...] = ("botName", "tags", "symbol", "description")
_V2_TIMESTAMP_FIELDS: tuple[str, ...] = ("expiration", "openDate", "closeDate")
_V2_NUMERIC_FIELDS: tuple[str, ...] = ("quantity", "openPrice", "closePrice", "pnl")

FINGERPRINT_V2_FIELDS: tuple[str, ...] = (
    "source",
    *_V2_TEXT_FIELDS,
    *_V2_TIMESTAMP_FIELDS,
    *_V2_NUMERIC_FIELDS,
)

_SEPARATOR = "\x1f"  # unit separator: cannot appear in CSV cell text
FINGERPRINT_VERSION_V1 = "oa1"
FINGERPRINT_VERSION_V2 = "oa2"


def _digest(parts: Iterable[str]) -> str:
    return hashlib.sha256(_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


def _norm_text(value: str | None) -> str:
    return value.strip() if value is not None else ""


def _norm_numeric(value: str | None) -> str:
    """Canonicalize numeric formatting: '3', '3.0', ' 3.00' hash equally."""
    from wolf_trading_os.ingestion.option_alpha import values

    if value is None or not value.strip():
        return ""
    try:
        parsed = values.parse_money(value)
    except ValueError:
        return value.strip()
    if parsed is None:
        return ""
    return format(parsed.normalize(), "f")


def _norm_timestamp(value: str | None) -> str:
    """Canonicalize timestamp formatting to ISO-8601 where parseable."""
    from wolf_trading_os.ingestion.option_alpha import values

    if value is None or not value.strip():
        return ""
    try:
        parsed = values.parse_timestamp(value)
    except ValueError:
        return value.strip()
    if parsed is None:
        return ""
    return parsed.local.isoformat()


def compute_fingerprint_v1(raw_row: dict[str, str | None]) -> str:
    """Legacy oa1 fingerprint (kept only to deduplicate against rows
    imported before the oa2 migration)."""
    parts = [FINGERPRINT_VERSION_V1]
    parts.extend(_norm_text(raw_row.get(field)) for field in FINGERPRINT_V1_FIELDS)
    return _digest(parts)


def compute_fingerprint_v2(
    raw_row: dict[str, str | None],
    *,
    source: str = "option_alpha",
    occurrence: int = 1,
) -> str:
    """Current oa2 fingerprint.

    ``occurrence`` is the 1-based index of this row among rows in the
    SAME FILE that share the same base identity (importer-assigned).
    """
    if occurrence < 1:
        raise ValueError(f"occurrence must be >= 1, got {occurrence}")
    parts = [FINGERPRINT_VERSION_V2, source]
    parts.extend(_norm_text(raw_row.get(f)) for f in _V2_TEXT_FIELDS)
    parts.extend(_norm_timestamp(raw_row.get(f)) for f in _V2_TIMESTAMP_FIELDS)
    parts.extend(_norm_numeric(raw_row.get(f)) for f in _V2_NUMERIC_FIELDS)
    parts.append(f"occ={occurrence}")
    return _digest(parts)


def base_identity_v2(raw_row: dict[str, str | None], *, source: str = "option_alpha") -> str:
    """Occurrence-independent identity key used by the importer to group
    repeated identical rows within one file."""
    return compute_fingerprint_v2(raw_row, source=source, occurrence=1)
