"""Bundle all analytics for a trade population in one call (dashboard/CLI)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

from wolf_trading_os.analytics import (
    CoreMetrics,
    EquityStats,
    ExcursionStats,
    NormalizedMetrics,
    closed_trades,
    core_metrics,
    equity_curve,
    excursion_stats,
    load_trades,
    normalized_metrics,
)
from wolf_trading_os.logging import get_logger

logger = get_logger(__name__)


def load_trades_safely(engine: object = None) -> tuple[pd.DataFrame | None, str | None]:
    """Load trades, converting database failures into a sanitized,
    user-facing error message (audit item 15).

    The message names only the exception CLASS — never the connection
    URL, credentials, or a stack trace. Full details go to the log.
    """
    try:
        return load_trades(engine), None  # type: ignore[arg-type]
    except SQLAlchemyError as exc:
        logger.error("trades_load_failed", error_type=type(exc).__name__)
        return None, (
            f"Database unavailable ({type(exc).__name__}). "
            "Check that PostgreSQL is running, then retry."
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
