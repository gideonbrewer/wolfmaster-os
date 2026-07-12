"""Row normalization: valid rows, malformed rows, derived fields."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from wolf_trading_os.domain import (
    AssetClass,
    Direction,
    InstrumentType,
    ParseSource,
    TradeEnvironment,
    TradeStatus,
)
from wolf_trading_os.ingestion.option_alpha.normalizer import normalize_row

VALID_ROW: dict[str, str | None] = {
    "botName": "Hulk 0DTE 0.50Δ 3x [Live]",
    "type": "iron butterfly",
    "description": "SPY Jan 5 2026 $595 Iron Butterfly",
    "symbol": "spy",
    "status": "closed",
    "quantity": "3",
    "daysInTrade": "0.19",
    "openPrice": "2.15",
    "closePrice": "0.85",
    "premium": "645.00",
    "pnl": "390.00",
    "ror": "60.47",
    "returnPct": "60.47",
    "risk": "645.00",
    "highReturnPct": "85.20",
    "lowReturnPct": "-32.50",
    "highReturnPctDate": "01/05/26 12:45",
    "lowReturnPctDate": "01/05/26 10:05",
    "expiration": "01/07/26",
    "openDate": "01/05/26 09:35",
    "closeDate": "01/05/26 14:12",
    "tags": "0dte,momentum",
    "underlyingOpen": "594.85",
    "underlyingClose": "596.10",
}


class TestValidRow:
    def test_accepted_and_mapped(self) -> None:
        outcome = normalize_row(dict(VALID_ROW), 1)
        assert outcome.accepted, outcome.errors
        trade = outcome.trade
        assert trade is not None
        assert trade.underlying_symbol == "SPY"  # uppercased
        assert trade.quantity == Decimal("3")
        assert trade.realized_pnl == Decimal("390.00")
        assert trade.opened_at == dt.datetime(2026, 1, 5, 9, 35)
        assert trade.closed_at == dt.datetime(2026, 1, 5, 14, 12)
        assert trade.status is TradeStatus.CLOSED
        assert trade.instrument_type is InstrumentType.IRON_BUTTERFLY
        assert trade.direction is Direction.CREDIT
        assert trade.asset_class is AssetClass.EQUITY_OPTION
        assert trade.environment is TradeEnvironment.LIVE
        assert trade.target_delta == Decimal("0.5")
        assert trade.dte_setting == 0
        assert trade.contract_count_setting == 3
        assert trade.mfe_pct == Decimal("85.20")
        assert trade.mae_pct == Decimal("-32.50")
        assert trade.tags == ("0dte", "momentum")

    def test_dte_at_entry_derived(self) -> None:
        outcome = normalize_row(dict(VALID_ROW), 1)
        assert outcome.trade is not None
        assert outcome.trade.dte_at_entry == 2  # 01/05 -> 01/07
        assert outcome.trade.parse_sources["dte_at_entry"] is ParseSource.DERIVED

    def test_raw_payload_preserved(self) -> None:
        outcome = normalize_row(dict(VALID_ROW), 1)
        assert outcome.trade is not None
        assert outcome.trade.raw_payload["openPrice"] == "2.15"
        assert outcome.trade.raw_payload["botName"] == VALID_ROW["botName"]


class TestRejections:
    def test_missing_symbol(self) -> None:
        outcome = normalize_row({**VALID_ROW, "symbol": ""}, 1)
        assert not outcome.accepted
        assert any("symbol" in e for e in outcome.errors)

    def test_invalid_open_date(self) -> None:
        outcome = normalize_row({**VALID_ROW, "openDate": "banana"}, 1)
        assert not outcome.accepted
        assert any("openDate" in e for e in outcome.errors)

    def test_invalid_quantity(self) -> None:
        outcome = normalize_row({**VALID_ROW, "quantity": "oops"}, 1)
        assert not outcome.accepted

    def test_negative_quantity(self) -> None:
        outcome = normalize_row({**VALID_ROW, "quantity": "-3"}, 1)
        assert not outcome.accepted

    def test_closed_trade_without_pnl(self) -> None:
        outcome = normalize_row({**VALID_ROW, "pnl": ""}, 1)
        assert not outcome.accepted
        assert any("pnl" in e for e in outcome.errors)

    def test_close_before_open(self) -> None:
        outcome = normalize_row({**VALID_ROW, "closeDate": "01/04/26 10:00"}, 1)
        assert not outcome.accepted


class TestTolerance:
    def test_open_trade_without_pnl_is_accepted(self) -> None:
        row = {**VALID_ROW, "status": "open", "pnl": "", "closeDate": "", "closePrice": ""}
        outcome = normalize_row(row, 1)
        assert outcome.accepted
        assert outcome.trade is not None
        assert outcome.trade.realized_pnl is None

    def test_bad_optional_value_warns_but_accepts(self) -> None:
        outcome = normalize_row({**VALID_ROW, "highReturnPct": "not-a-number"}, 1)
        assert outcome.accepted
        assert outcome.trade is not None
        assert outcome.trade.mfe_pct is None
        assert any("highReturnPct" in w for w in outcome.warnings)

    def test_unrecognized_type_warns(self) -> None:
        outcome = normalize_row({**VALID_ROW, "type": "quantum entanglement"}, 1)
        assert outcome.accepted
        assert outcome.trade is not None
        assert outcome.trade.instrument_type is InstrumentType.OTHER
        assert any("type" in w for w in outcome.warnings)

    def test_null_optionals(self) -> None:
        row = dict.fromkeys(VALID_ROW)
        row.update(
            {
                "botName": "Mystery",
                "symbol": "SPY",
                "quantity": "1",
                "openDate": "01/05/26 09:35",
                "pnl": "10",
            }
        )
        outcome = normalize_row(row, 1)
        assert outcome.accepted
        trade = outcome.trade
        assert trade is not None
        assert trade.premium is None
        assert trade.risk is None
        assert trade.expires_at is None
        assert trade.dte_at_entry is None
        assert trade.target_delta is None
        assert trade.environment is TradeEnvironment.UNKNOWN

    def test_environment_from_tags(self) -> None:
        row = {**VALID_ROW, "botName": "Plain Bot", "tags": "paper"}
        outcome = normalize_row(row, 1)
        assert outcome.trade is not None
        assert outcome.trade.environment is TradeEnvironment.PAPER
        assert outcome.trade.parse_sources["environment"] is ParseSource.TAGS
