"""Option Alpha CSV column schema: canonical names, aliases, requirements."""

from __future__ import annotations

import re

# Canonical (camelCase, as exported by Option Alpha) column names.
REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "botName",
        "symbol",
        "quantity",
        "openDate",
        "pnl",
    }
)

OPTIONAL_COLUMNS: frozenset[str] = frozenset(
    {
        "type",
        "description",
        "status",
        "daysInTrade",
        "openPrice",
        "closePrice",
        "premium",
        "ror",
        "returnPct",
        "risk",
        "ev",
        "alpha",
        "highReturnPct",
        "lowReturnPct",
        "highReturnPctDate",
        "lowReturnPctDate",
        "expiration",
        "closeDate",
        "tags",
        "underlyingOpen",
        "underlyingClose",
    }
)

KNOWN_COLUMNS: frozenset[str] = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


def _fold(name: str) -> str:
    """Fold a header for matching: lowercase, drop non-alphanumerics."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


_FOLDED_TO_CANONICAL: dict[str, str] = {_fold(c): c for c in KNOWN_COLUMNS}
# Common aliases seen in exports / spreadsheet round-trips.
_FOLDED_TO_CANONICAL.update(
    {
        _fold("bot"): "botName",
        _fold("bot_name"): "botName",
        _fold("p&l"): "pnl",
        _fold("profit"): "pnl",
        _fold("returnPercent"): "returnPct",
        _fold("qty"): "quantity",
        _fold("openedAt"): "openDate",
        _fold("closedAt"): "closeDate",
        _fold("expirationDate"): "expiration",
    }
)


def normalize_header(header: str) -> str | None:
    """Map a raw CSV header to its canonical column name, or None if unknown.

    Tolerates BOM, whitespace, case differences, and snake_case variants.
    """
    cleaned = header.lstrip("﻿").strip()
    return _FOLDED_TO_CANONICAL.get(_fold(cleaned))


def normalize_headers(headers: list[str]) -> tuple[dict[int, str], list[str]]:
    """Map column index -> canonical name; also return unrecognized headers."""
    mapping: dict[int, str] = {}
    unknown: list[str] = []
    for i, header in enumerate(headers):
        canonical = normalize_header(header)
        if canonical is None:
            unknown.append(header.strip())
        elif canonical in mapping.values():
            unknown.append(header.strip())  # duplicate column; keep first
        else:
            mapping[i] = canonical
    return mapping, unknown


def missing_required(present: set[str]) -> set[str]:
    return set(REQUIRED_COLUMNS) - present
