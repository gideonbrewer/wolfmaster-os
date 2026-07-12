"""Equity curve, running peak, drawdown, and durations."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from wolf_trading_os.analytics import equity_curve


def _df(pnls: list[float], day_offsets: list[int] | None = None) -> pd.DataFrame:
    base = dt.datetime(2026, 1, 5, 16, 0)
    offsets = day_offsets if day_offsets is not None else list(range(len(pnls)))
    return pd.DataFrame(
        {
            "realized_pnl": pnls,
            "opened_at": [base + dt.timedelta(days=o, hours=-6) for o in offsets],
            "closed_at": [base + dt.timedelta(days=o) for o in offsets],
        }
    )


class TestEquityCurve:
    def test_cumulative_and_peak(self) -> None:
        stats = equity_curve(_df([100, -50, 200, -300, 100]))
        assert stats.curve["equity"].tolist() == [100, 50, 250, -50, 50]
        assert stats.curve["peak"].tolist() == [100, 100, 250, 250, 250]
        assert stats.curve["drawdown"].tolist() == [0, 50, 0, 300, 200]

    def test_max_drawdown(self) -> None:
        stats = equity_curve(_df([100, -50, 200, -300, 100]))
        assert stats.max_drawdown == 300

    def test_max_drawdown_pct_only_when_peak_positive(self) -> None:
        stats = equity_curve(_df([100, -50, 200, -300, 100]))
        # dd 300 against peak 250 -> 120%
        assert stats.max_drawdown_pct == pytest.approx(120.0)

    def test_pct_none_when_peak_never_positive(self) -> None:
        stats = equity_curve(_df([-100, -50]))
        assert stats.max_drawdown == 150
        assert stats.max_drawdown_pct is None  # mathematically invalid -> fail closed

    def test_durations(self) -> None:
        # peak day0(100) -> trough day3, recovery day5
        stats = equity_curve(_df([100, -20, -30, -50, 60, 60], [0, 1, 2, 3, 4, 5]))
        assert stats.max_drawdown == 100
        assert stats.max_drawdown_duration_days == pytest.approx(3.0)
        assert stats.recovery_duration_days == pytest.approx(2.0)

    def test_unrecovered_drawdown(self) -> None:
        stats = equity_curve(_df([100, -80]))
        assert stats.recovery_duration_days is None

    def test_curve_ordered_by_close_time(self) -> None:
        df = _df([100, -50, 200])
        df.loc[2, "closed_at"] = dt.datetime(2026, 1, 1, 16, 0)  # closes first
        stats = equity_curve(df)
        assert stats.curve["equity"].tolist() == [200, 300, 250]

    def test_empty(self) -> None:
        stats = equity_curve(pd.DataFrame())
        assert stats.max_drawdown == 0.0
        assert stats.curve.empty
