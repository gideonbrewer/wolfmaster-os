"""Grouped breakdowns and comparisons."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from wolf_trading_os.analytics import enrich, grouped_metrics
from wolf_trading_os.analytics.grouping import compare_groups


def _df() -> pd.DataFrame:
    base = dt.datetime(2026, 1, 5, 10, 0)  # a Monday
    return pd.DataFrame(
        {
            "realized_pnl": [100.0, -50.0, 200.0, 300.0, None],
            "quantity": [1.0, 1.0, 2.0, 3.0, 1.0],
            "target_delta": [0.5, 0.5, 0.6, None, 0.5],
            "underlying_symbol": ["SPY", "SPY", "QQQ", "NVDA", "SPY"],
            "return_fraction": [10.0, -5.0, 20.0, 30.0, None],
            "opened_at": [base + dt.timedelta(days=i) for i in range(5)],
            "closed_at": [base + dt.timedelta(days=i, hours=3) for i in range(5)],
            "tags": [["a", "b"], ["a"], ["b"], [], ["a"]],
        }
    )


class TestGroupedMetrics:
    def test_by_delta(self) -> None:
        table = grouped_metrics(_df(), "target_delta")
        by_group = table.set_index("group")
        # 0.5: trades with pnl = +100, -50 (open trade has no pnl -> excluded)
        assert by_group.loc[0.5, "trade_count"] == 2
        assert by_group.loc[0.5, "total_pnl"] == 50.0
        assert by_group.loc[0.5, "win_rate"] == pytest.approx(0.5)
        assert by_group.loc[0.6, "trade_count"] == 1
        # Null delta rows form no group
        assert set(by_group.index) == {0.5, 0.6}

    def test_by_symbol_includes_normalized(self) -> None:
        table = grouped_metrics(_df(), "underlying_symbol").set_index("group")
        assert table.loc["QQQ", "per_contract_total_pnl"] == 100.0  # 200 / qty 2
        assert table.loc["NVDA", "per_contract_total_pnl"] == 100.0  # 300 / qty 3

    def test_by_day_of_week_uses_enriched_column(self) -> None:
        table = grouped_metrics(enrich(_df()), "day_of_week")
        assert "Monday" in set(table["group"])

    def test_tags_exploded(self) -> None:
        table = grouped_metrics(_df(), "tags").set_index("group")
        assert table.loc["a", "trade_count"] == 2  # +100, -50 (open excluded)
        assert table.loc["b", "trade_count"] == 2  # +100, +200

    def test_unsupported_column_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported grouping column"):
            grouped_metrics(_df(), "fingerprint")

    def test_empty(self) -> None:
        assert grouped_metrics(pd.DataFrame(), "underlying_symbol").empty


class TestCompareGroups:
    def test_restricts_to_requested_values(self) -> None:
        table = compare_groups(_df(), "underlying_symbol", ["SPY", "QQQ"])
        assert set(table["group"]) == {"SPY", "QQQ"}

    def test_delta_comparison(self) -> None:
        table = compare_groups(_df(), "target_delta", [0.5, 0.6])
        assert len(table) == 2
