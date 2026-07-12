"""Core performance metrics.

Population: trades with a non-null `realized_pnl` (closed trades).
Formulas are specified in docs/analytics-definitions.md; changing a
formula requires updating both the doc and the tests.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class CoreMetrics:
    trade_count: int
    total_pnl: float
    avg_pnl: float | None
    median_pnl: float | None
    wins: int
    losses: int
    flats: int
    win_rate: float | None  # wins / trade_count, 0..1
    avg_winner: float | None
    avg_loser: float | None  # negative
    payoff_ratio: float | None  # avg_winner / |avg_loser|
    gross_profit: float
    gross_loss: float  # positive magnitude
    profit_factor: float | None  # gross_profit / gross_loss; None if no losses
    expectancy: float | None  # mean P&L per trade
    avg_return_fraction: float | None
    median_return_fraction: float | None
    best_trade_pnl: float | None
    worst_trade_pnl: float | None
    max_consecutive_wins: int
    max_consecutive_losses: int


def core_metrics(df: pd.DataFrame) -> CoreMetrics:
    """Compute core metrics over trades that have a realized P&L."""
    pnl = df["realized_pnl"].dropna() if "realized_pnl" in df.columns else pd.Series(dtype=float)
    n = len(pnl)
    if n == 0:
        return CoreMetrics(
            trade_count=0,
            total_pnl=0.0,
            avg_pnl=None,
            median_pnl=None,
            wins=0,
            losses=0,
            flats=0,
            win_rate=None,
            avg_winner=None,
            avg_loser=None,
            payoff_ratio=None,
            gross_profit=0.0,
            gross_loss=0.0,
            profit_factor=None,
            expectancy=None,
            avg_return_fraction=None,
            median_return_fraction=None,
            best_trade_pnl=None,
            worst_trade_pnl=None,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
        )

    winners = pnl[pnl > 0]
    losers = pnl[pnl < 0]
    flats = pnl[pnl == 0]

    gross_profit = float(winners.sum())
    gross_loss = float(-losers.sum())
    avg_winner = float(winners.mean()) if len(winners) else None
    avg_loser = float(losers.mean()) if len(losers) else None

    payoff_ratio = (
        avg_winner / abs(avg_loser)
        if avg_winner is not None and avg_loser is not None and avg_loser != 0
        else None
    )
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    returns = (
        df.loc[pnl.index, "return_fraction"].dropna()
        if "return_fraction" in df.columns
        else pd.Series(dtype=float)
    )

    ordered = _ordered_pnl(df, pnl)
    max_wins = _max_streak(ordered, positive=True)
    max_losses = _max_streak(ordered, positive=False)

    return CoreMetrics(
        trade_count=n,
        total_pnl=float(pnl.sum()),
        avg_pnl=float(pnl.mean()),
        median_pnl=float(pnl.median()),
        wins=len(winners),
        losses=len(losers),
        flats=len(flats),
        win_rate=len(winners) / n,
        avg_winner=avg_winner,
        avg_loser=avg_loser,
        payoff_ratio=payoff_ratio,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        expectancy=float(pnl.mean()),
        avg_return_fraction=float(returns.mean()) if len(returns) else None,
        median_return_fraction=float(returns.median()) if len(returns) else None,
        best_trade_pnl=float(pnl.max()),
        worst_trade_pnl=float(pnl.min()),
        max_consecutive_wins=max_wins,
        max_consecutive_losses=max_losses,
    )


def _ordered_pnl(df: pd.DataFrame, pnl: pd.Series) -> pd.Series:
    """P&L ordered by close time (fallback: open time) for streak analysis."""
    sub = df.loc[pnl.index]
    if "closed_at" in sub.columns:
        order = sub["closed_at"].fillna(sub.get("opened_at"))
    elif "opened_at" in sub.columns:
        order = sub["opened_at"]
    else:
        return pnl
    return pnl.loc[order.sort_values(kind="stable").index]


def _max_streak(pnl: pd.Series, *, positive: bool) -> int:
    best = current = 0
    for value in pnl:
        if (value > 0) if positive else (value < 0):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best
