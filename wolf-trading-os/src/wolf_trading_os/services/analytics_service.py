"""Bundle all analytics for a trade population in one call (dashboard/CLI)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from wolf_trading_os.analytics import (
    CoreMetrics,
    EquityStats,
    ExcursionStats,
    NormalizedMetrics,
    closed_trades,
    core_metrics,
    equity_curve,
    excursion_stats,
    normalized_metrics,
)


@dataclass(frozen=True, slots=True)
class AnalyticsBundle:
    all_trades: pd.DataFrame
    closed: pd.DataFrame
    core: CoreMetrics
    normalized: NormalizedMetrics
    equity: EquityStats
    excursion: ExcursionStats


def build_analytics_bundle(df: pd.DataFrame) -> AnalyticsBundle:
    closed = closed_trades(df)
    return AnalyticsBundle(
        all_trades=df,
        closed=closed,
        core=core_metrics(closed),
        normalized=normalized_metrics(closed),
        equity=equity_curve(closed),
        excursion=excursion_stats(closed),
    )
