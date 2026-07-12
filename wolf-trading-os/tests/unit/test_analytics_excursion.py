"""MFE/MAE excursion statistics."""

from __future__ import annotations

import pandas as pd
import pytest

from wolf_trading_os.analytics import excursion_stats


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            #            A      B      C      D      E
            "mfe_pct": [60.0, 20.0, 8.0, 4.0, 55.0],
            "mae_pct": [-10.0, -30.0, -5.0, -60.0, -25.0],
            "return_pct": [50.0, -15.0, 2.0, -40.0, 0.0],
            "realized_pnl": [500.0, -150.0, 20.0, -400.0, 0.0],
        }
    )


class TestAggregates:
    def test_means_and_medians(self) -> None:
        s = excursion_stats(_df())
        assert s.trades_with_mfe == 5
        assert s.avg_mfe_pct == pytest.approx((60 + 20 + 8 + 4 + 55) / 5)
        assert s.median_mfe_pct == pytest.approx(20.0)
        assert s.avg_mae_pct == pytest.approx((-10 - 30 - 5 - 60 - 25) / 5)
        assert s.median_mae_pct == pytest.approx(-25.0)

    def test_capture_ratio_aggregate(self) -> None:
        s = excursion_stats(_df())
        # all five have mfe > 0: mean(return)=-0.6, mean(mfe)=29.4
        assert s.mfe_capture_ratio == pytest.approx(-0.6 / 29.4)

    def test_giveback(self) -> None:
        s = excursion_stats(_df())
        expected = ((60 - 50) + (20 - -15) + (8 - 2) + (4 - -40) + (55 - 0)) / 5
        assert s.avg_profit_giveback_pct == pytest.approx(expected)


class TestThresholds:
    def test_reached_counts(self) -> None:
        s = excursion_stats(_df())
        assert s.reached_threshold[5.0] == 4  # A, B, C, E
        assert s.reached_threshold[10.0] == 3  # A, B, E
        assert s.reached_threshold[20.0] == 3
        assert s.reached_threshold[25.0] == 2  # A, E
        assert s.reached_threshold[50.0] == 2

    def test_reached_but_closed_badly(self) -> None:
        s = excursion_stats(_df())
        # reached >= +5 MFE: A(50), B(-15), C(2), E(0)
        assert s.reached_but_closed_flat == 1  # E
        assert s.reached_but_closed_below_5pct == 1  # C
        assert s.reached_but_closed_negative == 1  # B

    def test_losers_previously_profitable(self) -> None:
        s = excursion_stats(_df())
        assert s.losers_previously_profitable == 2  # B and D

    def test_winners_with_adverse_excursion(self) -> None:
        s = excursion_stats(_df())
        # winners: A (mae -10), C (mae -5)
        assert s.winners_with_adverse_excursion[5.0] == 2
        assert s.winners_with_adverse_excursion[10.0] == 1
        assert s.winners_with_adverse_excursion[20.0] == 0


class TestEdgeCases:
    def test_empty(self) -> None:
        s = excursion_stats(pd.DataFrame())
        assert s.trades_with_mfe == 0
        assert s.mfe_capture_ratio is None
        assert s.avg_mfe_pct is None

    def test_missing_values_excluded(self) -> None:
        df = _df()
        df.loc[0, "mfe_pct"] = None
        s = excursion_stats(df)
        assert s.trades_with_mfe == 4
