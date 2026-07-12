"""Fingerprint determinism and stability."""

from __future__ import annotations

from wolf_trading_os.ingestion.option_alpha.fingerprint import (
    FINGERPRINT_FIELDS,
    compute_fingerprint,
)

_ROW = {
    "botName": "Hulk 0DTE 0.50Δ 3x [Live]",
    "type": "iron butterfly",
    "description": "SPY Jan 5 2026 $595 Iron Butterfly",
    "symbol": "SPY",
    "quantity": "3",
    "openDate": "01/05/26 09:35",
    "closeDate": "01/05/26 14:12",
    "expiration": "01/05/26",
    "openPrice": "2.15",
    "closePrice": "0.85",
    "premium": "645.00",
    "pnl": "390.00",
}


def test_deterministic() -> None:
    assert compute_fingerprint(dict(_ROW)) == compute_fingerprint(dict(_ROW))


def test_sha256_hex_shape() -> None:
    fp = compute_fingerprint(_ROW)
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_extra_columns_do_not_change_fingerprint() -> None:
    extended = {**_ROW, "ev": "112.50", "alpha": "38.2", "someNewColumn": "x"}
    assert compute_fingerprint(extended) == compute_fingerprint(_ROW)


def test_identifying_field_change_changes_fingerprint() -> None:
    for field in FINGERPRINT_FIELDS:
        mutated = {**_ROW, field: (_ROW.get(field) or "") + "_changed"}
        assert compute_fingerprint(mutated) != compute_fingerprint(_ROW), field


def test_missing_and_empty_are_equivalent() -> None:
    without = {k: v for k, v in _ROW.items() if k != "closePrice"}
    with_empty = {**_ROW, "closePrice": ""}
    assert compute_fingerprint(without) == compute_fingerprint(with_empty)


def test_whitespace_insensitive() -> None:
    padded = {k: f"  {v}  " for k, v in _ROW.items()}
    assert compute_fingerprint(padded) == compute_fingerprint(_ROW)
