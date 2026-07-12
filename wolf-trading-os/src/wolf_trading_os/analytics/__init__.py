"""Performance analytics.

All metric functions are pure functions over pandas DataFrames whose
columns follow the canonical trade schema (see `frames.py`). Exact
formulas are documented in docs/analytics-definitions.md and enforced by
tests/unit/test_analytics_*.py.
"""

from wolf_trading_os.analytics.core import CoreMetrics, core_metrics
from wolf_trading_os.analytics.equity import EquityStats, equity_curve
from wolf_trading_os.analytics.excursion import ExcursionStats, excursion_stats
from wolf_trading_os.analytics.frames import closed_trades, enrich, load_trades
from wolf_trading_os.analytics.grouping import grouped_metrics
from wolf_trading_os.analytics.normalization import NormalizedMetrics, normalized_metrics

__all__ = [
    "CoreMetrics",
    "EquityStats",
    "ExcursionStats",
    "NormalizedMetrics",
    "closed_trades",
    "core_metrics",
    "enrich",
    "equity_curve",
    "excursion_stats",
    "grouped_metrics",
    "load_trades",
    "normalized_metrics",
]
