"""Bot-name parsing: family, delta, DTE, timeframe, contracts, environment."""

from __future__ import annotations

from decimal import Decimal

import pytest

from wolf_trading_os.domain import ParseSource, TradeEnvironment
from wolf_trading_os.ingestion.option_alpha.bot_parser import parse_bot_name


class TestDeltaParsing:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Hulk 0DTE 0.50Δ 3x [Live]", Decimal("0.5")),
            ("Hulk .65Δ", Decimal("0.65")),
            ("Hulk 0.50 delta", Decimal("0.5")),
            ("Scalper 50Δ", Decimal("0.5")),
            ("Banshee 30 delta", Decimal("0.3")),
        ],
    )
    def test_parsed(self, name: str, expected: Decimal) -> None:
        attrs = parse_bot_name(name)
        assert attrs.target_delta == expected
        assert attrs.parse_sources["target_delta"] is ParseSource.BOT_NAME

    @pytest.mark.parametrize("name", ["Hulk 0DTE", "Plain Bot", "Delta Force"])
    def test_absent_stays_none(self, name: str) -> None:
        assert parse_bot_name(name).target_delta is None


class TestDteParsing:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [("Hulk 0DTE x3", 0), ("Hulk 1DTE", 1), ("IC 2DTE", 2), ("Theta 45 DTE", 45)],
    )
    def test_parsed(self, name: str, expected: int) -> None:
        attrs = parse_bot_name(name)
        assert attrs.dte_setting == expected
        assert attrs.parse_sources["dte_setting"] is ParseSource.BOT_NAME

    def test_absent(self) -> None:
        assert parse_bot_name("Hulk 0.5Δ").dte_setting is None


class TestTimeframeParsing:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Banshee Swing v2", "swing"),
            ("SPY intraday scalper", "intraday"),
            ("Wheel weekly", "weekly"),
            ("Multi-Day breakout", "multi-day"),
        ],
    )
    def test_explicit_tokens(self, name: str, expected: str) -> None:
        assert parse_bot_name(name).timeframe == expected

    def test_0dte_token_is_timeframe(self) -> None:
        attrs = parse_bot_name("Hulk 0DTE 0.5Δ")
        assert attrs.timeframe == "0DTE"
        assert attrs.parse_sources["timeframe"] is ParseSource.BOT_NAME

    def test_0dte_derived_from_dte_setting(self) -> None:
        # "0 DTE" (with space) is a DTE setting, not the literal 0DTE token;
        # the timeframe is then derived from dte_setting == 0.
        attrs = parse_bot_name("Hulk 0 DTE 0.5Δ")
        assert attrs.dte_setting == 0
        assert attrs.timeframe == "0DTE"
        assert attrs.parse_sources["timeframe"] is ParseSource.DERIVED

    def test_absent(self) -> None:
        assert parse_bot_name("Hulk 2DTE").timeframe is None


class TestContractCount:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [("Hulk 3x", 3), ("Hulk x5", 5), ("Hulk 10 contracts", 10)],
    )
    def test_parsed(self, name: str, expected: int) -> None:
        assert parse_bot_name(name).contract_count_setting == expected


class TestEnvironment:
    def test_live(self) -> None:
        assert parse_bot_name("Hulk [Live]").environment is TradeEnvironment.LIVE

    def test_paper(self) -> None:
        assert parse_bot_name("Hulk paper").environment is TradeEnvironment.PAPER

    def test_contradictory_markers_stay_unknown(self) -> None:
        assert parse_bot_name("live paper test").environment is TradeEnvironment.UNKNOWN

    def test_absent(self) -> None:
        assert parse_bot_name("Hulk 0DTE").environment is TradeEnvironment.UNKNOWN
        assert "environment" not in parse_bot_name("Hulk 0DTE").parse_sources

    def test_no_substring_match(self) -> None:
        # "Delivery" contains "live" but is not an environment marker.
        assert parse_bot_name("Delivery bot").environment is TradeEnvironment.UNKNOWN


class TestFamilyAndVersion:
    def test_family(self) -> None:
        attrs = parse_bot_name("Hulk 0DTE 0.50Δ 3x [Live]")
        assert attrs.strategy_family == "Hulk"

    def test_multiword_family(self) -> None:
        assert parse_bot_name("Iron Wolf 1DTE").strategy_family == "Iron Wolf"

    def test_version(self) -> None:
        attrs = parse_bot_name("Banshee Swing v2 30 delta 5x")
        assert attrs.strategy_version == "v2"
        assert attrs.strategy_family == "Banshee"

    def test_empty_name(self) -> None:
        attrs = parse_bot_name(None)
        assert attrs.strategy_family is None
        assert attrs.strategy_name is None
        assert attrs.parse_sources == {}
