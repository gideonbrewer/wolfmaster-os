"""CSV header normalization and required-column validation."""

from __future__ import annotations

from wolf_trading_os.ingestion.option_alpha.schema import (
    missing_required,
    normalize_header,
    normalize_headers,
)


def test_exact_headers() -> None:
    assert normalize_header("botName") == "botName"
    assert normalize_header("highReturnPctDate") == "highReturnPctDate"


def test_case_and_snake_case_tolerated() -> None:
    assert normalize_header("BOTNAME") == "botName"
    assert normalize_header("bot_name") == "botName"
    assert normalize_header("open_date") == "openDate"
    assert normalize_header(" Symbol ") == "symbol"


def test_bom_stripped() -> None:
    assert normalize_header("﻿botName") == "botName"


def test_aliases() -> None:
    assert normalize_header("P&L") == "pnl"
    assert normalize_header("qty") == "quantity"


def test_unknown_headers_reported() -> None:
    mapping, unknown = normalize_headers(["botName", "mysteryColumn", "symbol"])
    assert set(mapping.values()) == {"botName", "symbol"}
    assert unknown == ["mysteryColumn"]


def test_duplicate_header_keeps_first() -> None:
    mapping, unknown = normalize_headers(["symbol", "symbol"])
    assert list(mapping.values()) == ["symbol"]
    assert unknown == ["symbol"]


def test_missing_required() -> None:
    assert missing_required({"botName", "symbol", "quantity", "openDate", "pnl"}) == set()
    assert missing_required({"botName", "symbol"}) == {"quantity", "openDate", "pnl"}
