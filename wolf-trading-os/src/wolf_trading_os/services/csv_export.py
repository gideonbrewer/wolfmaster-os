"""Spreadsheet-safe CSV export (audit remediation M2).

Canonical stored data is NEVER mutated; sanitization applies only to
user-downloadable CSV bytes. Any string cell beginning with a character
that spreadsheet applications interpret as a formula trigger
(= + - @ TAB CR) is prefixed with a single apostrophe, the documented
convention Excel/Sheets/LibreOffice honor for literal text. Numeric
cells (including negative numbers) are unaffected because they are not
strings.
"""

from __future__ import annotations

import pandas as pd

_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value: object) -> object:
    """Neutralize a would-be spreadsheet formula in one cell."""
    if isinstance(value, str) and value.startswith(_FORMULA_TRIGGERS):
        return "'" + value
    if isinstance(value, list | tuple):
        # tag lists render as joined text in exports
        return ", ".join(str(sanitize_cell(v)) for v in value)
    return value


def safe_csv_bytes(df: pd.DataFrame) -> bytes:
    """Render a DataFrame to CSV with formula-injection protection.

    Only object/string columns are sanitized; numeric columns pass
    through untouched, so negative numbers stay numbers.
    """
    safe = df.copy()
    for column in safe.columns:
        # Covers both classic object columns and pandas>=3 "str" dtype.
        if pd.api.types.is_object_dtype(safe[column]) or pd.api.types.is_string_dtype(safe[column]):
            safe[column] = safe[column].astype(object).map(sanitize_cell)
    return safe.to_csv(index=False).encode("utf-8")
