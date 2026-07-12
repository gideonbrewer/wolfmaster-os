"""MFE/MAE excursion statistics (decimal-fraction units, ADR-018)."""

from __future__ import annotations

import pandas as pd
import pytest

from wolf_trading_os.analytics import excursion_stats


def _df() -> pd.DataFrame:
    # Fractions: 0.60 == +60%.
    return pd.DataFrame(
        {
            #                  A      B      C      D      E
            "mfe_fraction": [0.60, 0.20, 0.08, 0.04, 0.55],
            "mae_fraction": [-0.10, -0.30, -0.05, -0.60, -0.25],
            "return_fraction": [0.50, -0.15, 0.02, -0.40, 0.0],
            "realized_pnl": [500.0, -150.0, 20.0, -400.0, 0.0],
        }
    )


class TestAggregates:
    def test_means_and_medians(self) -> None:
        s = excursion_stats(_df())
        assert s.trades_with_mfe == 5
        assert s.avg_mfe_fraction == pytest.approx((0.60 + 0.20 + 0.08 + 0.04 + 0.55) / 5)
        assert s.median_mfe_fraction == pytest.approx(0.20)
        assert s.avg_mae_fraction == pytest.approx((-0.10 - 0.30 - 0.05 - 0.60 - 0.25) / 5)
        assert s.median_mae_fraction == pytest.approx(-0.25)

    def test_capture_ratio_aggregate(self) -> None:
        s = excursion_stats(_df())
        # all five have mfe > 0: mean(return)=-0.006, mean(mfe)=0.294
        assert s.mfe_capture_ratio == pytest.approx(-0.006 / 0.294)

    def test_capture_ratio_is_unit_invariant(self) -> None:
        # A ratio of two same-unit quantities: scaling both by 100 must
        # not change it (guards against unit regressions).
        df = _df()
        scaled = df.assign(
            mfe_fraction=df["mfe_fraction"] * 100,
            return_fraction=df["return_fraction"] * 100,
        )
        assert excursion_stats(df).mfe_capture_ratio == pytest.approx(
            excursion_stats(scaled).mfe_capture_ratio
        )

    def test_giveback(self) -> None:
        s = excursion_stats(_df())
        expected = (
            (0.60 - 0.50) + (0.20 - -0.15) + (0.08 - 0.02) + (0.04 - -0.40) + (0.55 - 0.0)
        ) / 5
        assert s.avg_profit_giveback_fraction == pytest.approx(expected)


class TestThresholds:
    def test_reached_counts(self) -> None:
        s = excursion_stats(_df())
        assert s.reached_threshold[0.05] == 4  # A, B, C, E
        assert s.reached_threshold[0.10] == 3  # A, B, E
        assert s.reached_threshold[0.20] == 3
        assert s.reached_threshold[0.25] == 2  # A, E
        assert s.reached_threshold[0.50] == 2

    def test_reached_but_closed_badly(self) -> None:
        s = excursion_stats(_df())
        # reached >= +5% MFE: A(+50%), B(-15%), C(+2%), E(0%)
        assert s.reached_but_closed_flat == 1  # E
        assert s.reached_but_closed_below_5pct == 1  # C
        assert s.reached_but_closed_negative == 1  # B

    def test_losers_previously_profitable(self) -> None:
        s = excursion_stats(_df())
        assert s.losers_previously_profitable == 2  # B and D

    def test_winners_with_adverse_excursion(self) -> None:
        s = excursion_stats(_df())
        # winners: A (mae -10%), C (mae -5%)
        assert s.winners_with_adverse_excursion[0.05] == 2
        assert s.winners_with_adverse_excursion[0.10] == 1
        assert s.winners_with_adverse_excursion[0.20] == 0


class TestEdgeCases:
    def test_empty(self) -> None:
        s = excursion_stats(pd.DataFrame())
        assert s.trades_with_mfe == 0
        assert s.mfe_capture_ratio is None
        assert s.avg_mfe_fraction is None

    def test_missing_values_excluded(self) -> None:
        df = _df()
        df.loc[0, "mfe_fraction"] = None
        s = excursion_stats(df)
        assert s.trades_with_mfe == 4
