"""Quantity/capital normalization — raw vs normalized must diverge correctly."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from wolf_trading_os.analytics import normalized_metrics
from wolf_trading_os.analytics.normalization import (
    capital_deployed,
    per_contract_pnl,
    pnl_per_1k,
)


def _df() -> pd.DataFrame:
    base = dt.datetime(2026, 1, 5, 10, 0)
    return pd.DataFrame(
        {
            #                 A       B      C (no qty)  D (open)
            "realized_pnl": [300.0, -100.0, 50.0, None],
            "quantity": [3.0, 1.0, None, 2.0],
            "risk": [600.0, None, 500.0, 400.0],
            "premium": [None, -250.0, 100.0, None],
            "return_fraction": [50.0, -40.0, 10.0, None],
            "return_on_risk": [50.0, -40.0, 10.0, None],
            "opened_at": [base + dt.timedelta(days=i) for i in range(4)],
            "closed_at": [base + dt.timedelta(days=i, hours=2) for i in range(4)],
        }
    )


class TestPerContract:
    def test_values(self) -> None:
        ppc = per_contract_pnl(_df())
        # A: 300/3=100, B: -100/1=-100 ; C lacks quantity, D lacks pnl
        assert sorted(ppc.tolist()) == [-100.0, 100.0]

    def test_raw_and_normalized_diverge(self) -> None:
        m = normalized_metrics(_df())
        assert m.raw_total_pnl == 250.0  # 300 - 100 + 50
        assert m.per_contract_total_pnl == 0.0  # 100 - 100
        # Raw says profitable; per-contract says flat — the distinction the
        # normalization layer exists to expose.
        assert m.raw_total_pnl != m.per_contract_total_pnl


class TestCapital:
    def test_risk_preferred_premium_fallback(self) -> None:
        capital = capital_deployed(_df())
        # A: risk 600; B: no risk -> |premium| 250; C: risk 500; D: risk 400
        assert capital.tolist() == [600.0, 250.0, 500.0, 400.0]

    def test_pnl_per_1k(self) -> None:
        per_1k = pnl_per_1k(_df())
        # A: 300/600*1000=500, B: -100/250*1000=-400, C: 50/500*1000=100
        assert per_1k.tolist() == pytest.approx([500.0, -400.0, 100.0])

    def test_aggregate_per_1k_excludes_open_trades(self) -> None:
        m = normalized_metrics(_df())
        # capital with realized pnl: 600+250+500=1350; pnl 250
        assert m.total_capital_deployed == 1350.0
        assert m.pnl_per_1k_deployed == pytest.approx(250.0 / 1350.0 * 1000.0)


class TestEqualWeighted:
    def test_mean_of_returns(self) -> None:
        m = normalized_metrics(_df())
        assert m.equal_weighted_avg_return_fraction == pytest.approx((50 - 40 + 10) / 3)
        assert m.avg_return_on_risk == pytest.approx((50 - 40 + 10) / 3)

    def test_empty(self) -> None:
        m = normalized_metrics(pd.DataFrame())
        assert m.raw_total_pnl == 0.0
        assert m.per_contract_total_pnl is None
        assert m.equal_weighted_avg_return_fraction is None
