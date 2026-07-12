"""Bot-name parsing: family, delta, DTE, timeframe, contracts, environment.

Environment markers must be DELIMITED ([Live], (paper), "- Live",
"Live:") — brand words are never environment markers (H2). Conflicting
attribute matches fail closed to None/UNKNOWN with warnings (M8).
"""

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

    def test_equivalent_notations_do_not_conflict(self) -> None:
        # 0.50Δ and "50 delta" are the same value -> no conflict.
        attrs = parse_bot_name("Hulk 0.50Δ 50 delta")
        assert attrs.target_delta == Decimal("0.5")
        assert not attrs.warnings

    def test_conflicting_deltas_fail_closed(self) -> None:
        attrs = parse_bot_name("Hulk 0.50Δ and 0.65Δ variant")
        assert attrs.target_delta is None
        assert any("target_delta" in w for w in attrs.warnings)


class TestDteParsing:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [("Hulk 0DTE x3", 0), ("Hulk 1DTE", 1), ("IC 2DTE", 2), ("Theta 45 DTE", 45)],
    )
    def test_parsed(self, name: str, expected: int) -> None:
        attrs = parse_bot_name(name)
        assert attrs.dte_setting == expected
        assert attrs.parse_sources["dte_setting"] is ParseSource.BOT_NAME

    def test_conflicting_dtes_fail_closed(self) -> None:
        attrs = parse_bot_name("Hulk 0DTE 2DTE hybrid")
        assert attrs.dte_setting is None
        assert any("dte_setting" in w for w in attrs.warnings)

    def test_absent(self) -> None:
        assert parse_bot_name("Hulk 0.5Δ").dte_setting is None


class TestTimeframeParsing:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Banshee Swing v2", "swing"),
            ("SPY 30 delta scalper bot", "intraday"),
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
        attrs = parse_bot_name("Hulk 0 DTE 0.5Δ")
        assert attrs.dte_setting == 0
        assert attrs.timeframe == "0DTE"
        assert attrs.parse_sources["timeframe"] is ParseSource.DERIVED

    def test_conflicting_timeframes_fail_closed(self) -> None:
        attrs = parse_bot_name("Swing weekly hybrid bot")
        assert attrs.timeframe is None
        assert any("timeframe" in w for w in attrs.warnings)

    def test_absent(self) -> None:
        assert parse_bot_name("Hulk 2DTE").timeframe is None


class TestContractCount:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [("Hulk 3x", 3), ("Hulk x5", 5), ("Hulk 10 contracts", 10)],
    )
    def test_parsed(self, name: str, expected: int) -> None:
        assert parse_bot_name(name).contract_count_setting == expected

    def test_conflicting_counts_fail_closed(self) -> None:
        attrs = parse_bot_name("Hulk 2x 5 contracts")
        assert attrs.contract_count_setting is None
        assert any("contract_count_setting" in w for w in attrs.warnings)


class TestEnvironment:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Hulk [Live]", TradeEnvironment.LIVE),
            ("Hulk [ live ]", TradeEnvironment.LIVE),
            ("Hulk (Paper)", TradeEnvironment.PAPER),
            ("Hulk - Paper", TradeEnvironment.PAPER),
            ("Hulk - Live", TradeEnvironment.LIVE),
            ("Live: Hulk momentum", TradeEnvironment.LIVE),
            ("HULK [LIVE]", TradeEnvironment.LIVE),
        ],
    )
    def test_delimited_markers(self, name: str, expected: TradeEnvironment) -> None:
        assert parse_bot_name(name).environment is expected

    @pytest.mark.parametrize(
        "name",
        [
            "Live Wire Momentum",  # brand word, not a marker (H2)
            "Paper Tiger",
            "Deliver 0DTE",
            "Papertrail Swing",
            "Hulk live",  # bare word: not delimited -> not a marker
        ],
    )
    def test_brand_words_stay_unknown(self, name: str) -> None:
        assert parse_bot_name(name).environment is TradeEnvironment.UNKNOWN

    def test_contradictory_markers_stay_unknown_with_warning(self) -> None:
        attrs = parse_bot_name("Hulk [Live] (paper) test")
        assert attrs.environment is TradeEnvironment.UNKNOWN
        assert any("live/paper" in w for w in attrs.warnings)

    def test_absent(self) -> None:
        attrs = parse_bot_name("Hulk 0DTE")
        assert attrs.environment is TradeEnvironment.UNKNOWN
        assert "environment" not in attrs.parse_sources


class TestFamilyAndVersion:
    def test_family(self) -> None:
        assert parse_bot_name("Hulk 0DTE 0.50Δ 3x [Live]").strategy_family == "Hulk"

    def test_multiword_family(self) -> None:
        assert parse_bot_name("Iron Wolf 1DTE").strategy_family == "Iron Wolf"

    def test_brand_words_kept_in_family(self) -> None:
        assert parse_bot_name("Live Wire Momentum").strategy_family == "Live Wire Momentum"
        assert parse_bot_name("Paper Tiger").strategy_family == "Paper Tiger"

    def test_env_marker_not_in_family(self) -> None:
        assert parse_bot_name("Hulk [Live] 0DTE").strategy_family == "Hulk"

    def test_version(self) -> None:
        attrs = parse_bot_name("Banshee Swing v2 30 delta 5x")
        assert attrs.strategy_version == "v2"
        assert attrs.strategy_family == "Banshee"

    def test_unrelated_numbers_ignored(self) -> None:
        attrs = parse_bot_name("Area 51 breakout")
        assert attrs.strategy_family == "Area"
        assert attrs.target_delta is None
        assert attrs.dte_setting is None
        assert attrs.contract_count_setting is None

    def test_whitespace_tolerated(self) -> None:
        attrs = parse_bot_name("   Hulk   0DTE   0.50Δ   [Live]  ")
        assert attrs.strategy_family == "Hulk"
        assert attrs.environment is TradeEnvironment.LIVE

    def test_empty_name(self) -> None:
        attrs = parse_bot_name(None)
        assert attrs.strategy_family is None
        assert attrs.strategy_name is None
        assert attrs.parse_sources == {}
