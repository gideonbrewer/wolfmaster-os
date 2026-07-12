"""Fingerprint v1/v2 determinism, normalization, and identity separation."""

from __future__ import annotations

import pytest

from wolf_trading_os.ingestion.option_alpha.fingerprint import (
    FINGERPRINT_V1_FIELDS,
    FINGERPRINT_V2_FIELDS,
    base_identity_v2,
    compute_fingerprint_v1,
    compute_fingerprint_v2,
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
    "tags": "0dte,momentum",
}


class TestV2Determinism:
    def test_deterministic(self) -> None:
        assert compute_fingerprint_v2(dict(_ROW)) == compute_fingerprint_v2(dict(_ROW))

    def test_sha256_hex_shape(self) -> None:
        fp = compute_fingerprint_v2(_ROW)
        assert len(fp) == 64 and all(c in "0123456789abcdef" for c in fp)

    def test_differs_from_v1(self) -> None:
        assert compute_fingerprint_v2(_ROW) != compute_fingerprint_v1(_ROW)

    def test_extra_columns_ignored(self) -> None:
        extended = {**_ROW, "ev": "112.50", "alpha": "38.2", "brandNewColumn": "x"}
        assert compute_fingerprint_v2(extended) == compute_fingerprint_v2(_ROW)

    def test_analytic_fields_excluded(self) -> None:
        """Restated analytics (premium/risk/ror/MFE...) do not change identity."""
        for column in ("premium", "risk", "ror", "returnPct", "highReturnPct", "type", "status"):
            mutated = {**_ROW, column: "999"}
            assert compute_fingerprint_v2(mutated) == compute_fingerprint_v2(_ROW), column

    def test_identity_fields_included(self) -> None:
        for column in (
            "botName",
            "tags",
            "symbol",
            "description",
            "expiration",
            "openDate",
            "closeDate",
            "quantity",
            "openPrice",
            "closePrice",
            "pnl",
        ):
            mutated = {**_ROW, column: "7777"}
            assert compute_fingerprint_v2(mutated) != compute_fingerprint_v2(_ROW), column


class TestV2Normalization:
    def test_equivalent_numeric_formatting_deduplicates(self) -> None:
        variants = {**_ROW, "quantity": "3.0", "pnl": "$390", "openPrice": "2.1500"}
        assert compute_fingerprint_v2(variants) == compute_fingerprint_v2(_ROW)

    def test_equivalent_timestamp_formatting_deduplicates(self) -> None:
        variants = {**_ROW, "openDate": "2026-01-05 09:35", "expiration": "2026-01-05"}
        assert compute_fingerprint_v2(variants) == compute_fingerprint_v2(_ROW)

    def test_whitespace_insensitive(self) -> None:
        padded = {k: f"  {v}  " for k, v in _ROW.items()}
        assert compute_fingerprint_v2(padded) == compute_fingerprint_v2(_ROW)

    def test_missing_and_empty_equivalent(self) -> None:
        without = {k: v for k, v in _ROW.items() if k != "closePrice"}
        with_empty = {**_ROW, "closePrice": ""}
        assert compute_fingerprint_v2(without) == compute_fingerprint_v2(with_empty)


class TestV2IdentitySeparation:
    def test_different_bots_do_not_collide(self) -> None:
        other_bot = {**_ROW, "botName": "Banshee 0DTE 0.50Δ 3x [Live]"}
        assert compute_fingerprint_v2(other_bot) != compute_fingerprint_v2(_ROW)

    def test_live_and_paper_tags_do_not_collide(self) -> None:
        live = {**_ROW, "tags": "live"}
        paper = {**_ROW, "tags": "paper"}
        assert compute_fingerprint_v2(live) != compute_fingerprint_v2(paper)

    def test_source_discriminates(self) -> None:
        assert compute_fingerprint_v2(_ROW, source="option_alpha") != compute_fingerprint_v2(
            _ROW, source="manual"
        )


class TestOccurrence:
    def test_occurrences_distinct_and_deterministic(self) -> None:
        first = compute_fingerprint_v2(_ROW, occurrence=1)
        second = compute_fingerprint_v2(_ROW, occurrence=2)
        assert first != second
        assert second == compute_fingerprint_v2(_ROW, occurrence=2)

    def test_occurrence_one_is_base_identity(self) -> None:
        assert compute_fingerprint_v2(_ROW, occurrence=1) == base_identity_v2(_ROW)

    def test_invalid_occurrence_rejected(self) -> None:
        with pytest.raises(ValueError, match="occurrence"):
            compute_fingerprint_v2(_ROW, occurrence=0)


class TestV1Legacy:
    def test_v1_stable_field_list(self) -> None:
        # oa1 must never change: it deduplicates against pre-migration rows.
        assert FINGERPRINT_V1_FIELDS == (
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

    def test_v1_deterministic(self) -> None:
        assert compute_fingerprint_v1(dict(_ROW)) == compute_fingerprint_v1(dict(_ROW))

    def test_v2_field_list_documented(self) -> None:
        assert set(FINGERPRINT_V2_FIELDS) == {
            "source",
            "botName",
            "tags",
            "symbol",
            "description",
            "expiration",
            "openDate",
            "closeDate",
            "quantity",
            "openPrice",
            "closePrice",
            "pnl",
        }
