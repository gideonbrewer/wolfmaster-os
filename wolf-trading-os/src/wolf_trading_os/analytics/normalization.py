"""Position-size normalization.

Raw-dollar results must never be presented as equivalent to underlying
strategy quality when contract quantities differ — these metrics exist to
make the distinction explicit. Definitions in docs/analytics-definitions.md:

- per-contract P&L: realized_pnl / quantity, per trade
- capital deployed: risk when present, else |premium| (per trade)
- P&L per $1,000 deployed: realized_pnl / capital_deployed * 1000
- equal-weighted return: mean of per-trade return_fraction (each trade counts
  once regardless of size)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class NormalizedMetrics:
    # Raw dollars (size-dependent)
    raw_total_pnl: float
    raw_avg_pnl: float | None
    # Quantity-normalized (1-contract equivalent)
    per_contract_total_pnl: float | None
    per_contract_avg_pnl: float | None
    per_contract_median_pnl: float | None
    # Capital-normalized
    total_capital_deployed: float | None
    pnl_per_1k_deployed: float | None  # aggregate: total pnl / total capital * 1000
    avg_pnl_per_1k_deployed: float | None  # mean of per-trade values
    avg_return_on_risk: float | None
    # Equal-weighted
    equal_weighted_avg_return_fraction: float | None
    equal_weighted_median_return_fraction: float | None
    trades_with_quantity: int
    trades_with_capital: int


def per_contract_pnl(df: pd.DataFrame) -> pd.Series:
    """realized_pnl / quantity for trades where both are known and quantity > 0."""
    if "realized_pnl" not in df.columns or "quantity" not in df.columns:
        return pd.Series(dtype=float)
    sub = df[["realized_pnl", "quantity"]].dropna()
    sub = sub[sub["quantity"] > 0]
    result = sub["realized_pnl"] / sub["quantity"]
    return result.astype(float)


def capital_deployed(df: pd.DataFrame) -> pd.Series:
    """Per-trade capital deployed: `risk` when present, else |premium|."""
    if df.empty:
        return pd.Series(dtype=float)
    risk = df.get("risk", pd.Series(dtype=float, index=df.index))
    premium = df.get("premium", pd.Series(dtype=float, index=df.index))
    capital = risk.where(risk.notna() & (risk > 0), premium.abs())
    capital = capital[capital.notna() & (capital > 0)]
    return capital.astype(float)


def pnl_per_1k(df: pd.DataFrame) -> pd.Series:
    """Per-trade realized P&L per $1,000 of capital deployed."""
    if "realized_pnl" not in df.columns:
        return pd.Series(dtype=float)
    capital = capital_deployed(df)
    pnl = df.loc[capital.index, "realized_pnl"]
    mask = pnl.notna()
    result: pd.Series = (pnl[mask] / capital[mask] * 1000.0).astype(float)
    return result


def normalized_metrics(df: pd.DataFrame) -> NormalizedMetrics:
    pnl = df["realized_pnl"].dropna() if "realized_pnl" in df.columns else pd.Series(dtype=float)

    ppc = per_contract_pnl(df)
    per_1k = pnl_per_1k(df)
    capital = capital_deployed(df)
    # Only capital backing trades that actually have a realized P&L.
    capital_realized = (
        capital[df.loc[capital.index, "realized_pnl"].notna()] if len(capital) else capital
    )

    returns = (
        df["return_fraction"].dropna()
        if "return_fraction" in df.columns
        else pd.Series(dtype=float)
    )
    ror = (
        df["return_on_risk"].dropna() if "return_on_risk" in df.columns else pd.Series(dtype=float)
    )

    total_capital = float(capital_realized.sum()) if len(capital_realized) else None
    aggregate_per_1k = (
        float(pnl.loc[capital_realized.index].sum() / total_capital * 1000.0)
        if total_capital
        else None
    )

    return NormalizedMetrics(
        raw_total_pnl=float(pnl.sum()) if len(pnl) else 0.0,
        raw_avg_pnl=float(pnl.mean()) if len(pnl) else None,
        per_contract_total_pnl=float(ppc.sum()) if len(ppc) else None,
        per_contract_avg_pnl=float(ppc.mean()) if len(ppc) else None,
        per_contract_median_pnl=float(ppc.median()) if len(ppc) else None,
        total_capital_deployed=total_capital,
        pnl_per_1k_deployed=aggregate_per_1k,
        avg_pnl_per_1k_deployed=float(per_1k.mean()) if len(per_1k) else None,
        avg_return_on_risk=float(ror.mean()) if len(ror) else None,
        equal_weighted_avg_return_fraction=float(returns.mean()) if len(returns) else None,
        equal_weighted_median_return_fraction=float(returns.median()) if len(returns) else None,
        trades_with_quantity=len(ppc),
        trades_with_capital=len(per_1k),
    )


def equity_curve_normalized(df: pd.DataFrame) -> pd.Series:
    """Cumulative per-contract P&L in close-time order (1-contract equivalent)."""
    ppc = per_contract_pnl(df)
    if ppc.empty:
        return ppc
    order = df.loc[ppc.index, "closed_at"].fillna(df.loc[ppc.index, "opened_at"])
    ordered = ppc.loc[order.sort_values(kind="stable").index]
    curve: pd.Series = ordered.cumsum().astype(float).replace([np.inf, -np.inf], np.nan)
    return curve
