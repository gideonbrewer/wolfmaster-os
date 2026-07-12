"""Deterministic trade fingerprinting for duplicate detection.

The fingerprint is a SHA-256 hex digest over a FIXED list of identifying
fields taken from the normalized raw row. The field list is frozen: adding
or removing columns from an export does not change existing fingerprints,
so overlapping re-exports deduplicate correctly.

Documented in docs/data-model.md. Changing this list is a breaking change
that requires a migration strategy for existing fingerprints.
"""

from __future__ import annotations

import hashlib

FINGERPRINT_FIELDS: tuple[str, ...] = (
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

_SEPARATOR = "\x1f"  # unit separator: cannot appear in CSV cell text
_VERSION_PREFIX = "oa1"  # bump if the field list or normalization changes


def compute_fingerprint(raw_row: dict[str, str | None]) -> str:
    """SHA-256 fingerprint of one normalized raw CSV row.

    `raw_row` must be keyed by canonical column names. Missing fields and
    empty strings are equivalent; values are whitespace-trimmed but not
    otherwise transformed.
    """
    parts = [_VERSION_PREFIX]
    for field in FINGERPRINT_FIELDS:
        value = raw_row.get(field)
        parts.append(value.strip() if value is not None else "")
    payload = _SEPARATOR.join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
