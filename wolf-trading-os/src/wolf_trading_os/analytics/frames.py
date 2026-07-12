"""Loading canonical trades into pandas DataFrames and shared enrichment.

Numeric database values (Decimal) are converted to float64 for analytics.
Derived columns added by `enrich()` are the single shared definition used
by both grouped analytics and the dashboard.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, select

from wolf_trading_os.database import get_engine
from wolf_trading_os.database.orm import TradeRow

NUMERIC_COLUMNS = [
    "quantity",
    "days_in_trade",
    "entry_price",
    "exit_price",
    "premium",
    "risk",
    "realized_pnl",
    "return_pct",
    "return_on_risk",
    "mfe_pct",
    "mae_pct",
    "underlying_entry_price",
    "underlying_exit_price",
    "target_delta",
]

_QUANTITY_BUCKETS: list[tuple[float, float, str]] = [
    (0, 1, "1"),
    (1, 2, "2"),
    (2, 4, "3-4"),
    (4, 9, "5-9"),
    (9, float("inf"), "10+"),
]


def load_trades(engine: Engine | None = None) -> pd.DataFrame:
    """Load all trades into an enriched DataFrame."""
    engine = engine or get_engine()
    df = pd.read_sql(select(TradeRow), engine)
    return enrich(df)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce dtypes and add derived analysis columns (see data-model.md)."""
    df = df.copy()
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("opened_at", "closed_at", "expires_at", "mfe_at", "mae_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "opened_at" in df.columns:
        df["entry_hour"] = df["opened_at"].dt.hour
        df["day_of_week"] = df["opened_at"].dt.day_name()
        df["month"] = df["opened_at"].dt.strftime("%Y-%m")
    if "closed_at" in df.columns:
        df["exit_hour"] = df["closed_at"].dt.hour
    if "quantity" in df.columns:
        df["quantity_bucket"] = df["quantity"].map(_quantity_bucket)
    return df


def closed_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Trades with a realized outcome — the population for all performance
    metrics. Open/unknown trades never contaminate performance numbers."""
    if df.empty or "realized_pnl" not in df.columns:
        return df.iloc[0:0]
    return df[df["realized_pnl"].notna()]


def _quantity_bucket(quantity: float | None) -> str | None:
    if quantity is None or pd.isna(quantity):
        return None
    for low, high, label in _QUANTITY_BUCKETS:
        if low < quantity <= high:
            return label
    return None
