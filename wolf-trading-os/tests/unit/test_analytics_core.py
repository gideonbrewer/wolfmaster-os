"""Core metrics against hand-computed values."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from wolf_trading_os.analytics import core_metrics


def _df(pnls: list[float | None], returns: list[float | None] | None = None) -> pd.DataFrame:
    base = dt.datetime(2026, 1, 5, 10, 0)
    n = len(pnls)
    return pd.DataFrame(
        {
            "realized_pnl": pnls,
            "return_pct": returns if returns is not None else [None] * n,
            "opened_at": [base + dt.timedelta(days=i) for i in range(n)],
            "closed_at": [base + dt.timedelta(days=i, hours=4) for i in range(n)],
        }
    )


class TestCoreMetrics:
    def test_hand_computed_example(self) -> None:
        # pnl: +100, +300, -200, 0, -100  → total 100
        m = core_metrics(_df([100, 300, -200, 0, -100], [10.0, 30.0, -20.0, 0.0, -10.0]))
        assert m.trade_count == 5
        assert m.total_pnl == 100
        assert m.avg_pnl == 20
        assert m.median_pnl == 0
        assert m.wins == 2 and m.losses == 2 and m.flats == 1
        assert m.win_rate == pytest.approx(0.4)
        assert m.avg_winner == 200
        assert m.avg_loser == -150
        assert m.payoff_ratio == pytest.approx(200 / 150)
        assert m.gross_profit == 400
        assert m.gross_loss == 300
        assert m.profit_factor == pytest.approx(400 / 300)
        assert m.expectancy == pytest.approx(20)
        assert m.avg_return_pct == pytest.approx(2.0)
        assert m.median_return_pct == pytest.approx(0.0)
        assert m.best_trade_pnl == 300
        assert m.worst_trade_pnl == -200

    def test_expectancy_equals_winrate_identity(self) -> None:
        # expectancy = win_rate*avg_winner + loss_rate*avg_loser (+ flats*0)
        m = core_metrics(_df([100, 300, -200, -100]))
        assert m.win_rate is not None and m.avg_winner is not None and m.avg_loser is not None
        identity = m.win_rate * m.avg_winner + (m.losses / m.trade_count) * m.avg_loser
        assert m.expectancy == pytest.approx(identity)

    def test_profit_factor_none_without_losses(self) -> None:
        m = core_metrics(_df([100, 50]))
        assert m.profit_factor is None
        assert m.gross_loss == 0

    def test_open_trades_excluded(self) -> None:
        m = core_metrics(_df([100, None, -50]))
        assert m.trade_count == 2
        assert m.total_pnl == 50

    def test_empty(self) -> None:
        m = core_metrics(_df([]))
        assert m.trade_count == 0
        assert m.total_pnl == 0.0
        assert m.win_rate is None
        assert m.expectancy is None

    def test_streaks_ordered_by_close_time(self) -> None:
        # close-time order: +,+,+,-,-,+  → max wins 3, max losses 2
        df = _df([100, 100, 100, -50, -50, 100])
        m = core_metrics(df)
        assert m.max_consecutive_wins == 3
        assert m.max_consecutive_losses == 2

    def test_streaks_use_close_order_not_row_order(self) -> None:
        df = _df([100, 100, -50])
        # Make the loss close FIRST -> sequence -,+,+
        df.loc[2, "closed_at"] = dt.datetime(2026, 1, 1, 10, 0)
        m = core_metrics(df)
        assert m.max_consecutive_wins == 2
        assert m.max_consecutive_losses == 1

    def test_flat_breaks_streak(self) -> None:
        m = core_metrics(_df([100, 0, 100]))
        assert m.max_consecutive_wins == 1
