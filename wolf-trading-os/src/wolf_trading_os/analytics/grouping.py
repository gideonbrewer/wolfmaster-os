"""Grouped performance breakdowns.

`grouped_metrics(df, by)` computes per-group core + normalized metrics for
any canonical or enriched column: bot_name, strategy_family,
strategy_version, underlying_symbol, asset_class, instrument_type,
target_delta, dte_setting / dte_at_entry, timeframe, entry_hour,
exit_hour, day_of_week, month, quantity / quantity_bucket, environment,
or exploded tags (`by="tags"`).
"""

from __future__ import annotations

import pandas as pd

from wolf_trading_os.analytics.core import core_metrics
from wolf_trading_os.analytics.normalization import capital_deployed, per_contract_pnl

GROUPABLE_COLUMNS: tuple[str, ...] = (
    "bot_name",
    "strategy_family",
    "strategy_version",
    "underlying_symbol",
    "asset_class",
    "instrument_type",
    "target_delta",
    "dte_setting",
    "dte_at_entry",
    "timeframe",
    "entry_hour",
    "exit_hour",
    "day_of_week",
    "month",
    "quantity",
    "quantity_bucket",
    "environment",
    "tags",
)


def grouped_metrics(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Per-group metrics table, sorted by total P&L descending.

    Rows with a null group key are excluded (they form no meaningful
    group; values are never invented).
    """
    if by not in GROUPABLE_COLUMNS:
        raise ValueError(f"unsupported grouping column: {by!r}")

    if by == "tags":
        df = df.explode("tags").rename(columns={"tags": "_tag"})
        by = "_tag"

    if df.empty or by not in df.columns:
        return pd.DataFrame()

    sub = df[df[by].notna()]
    records: list[dict[str, object]] = []
    for key, group in sub.groupby(by, sort=False):
        m = core_metrics(group)
        if m.trade_count == 0:
            continue
        ppc = per_contract_pnl(group)
        capital = capital_deployed(group)
        records.append(
            {
                "group": key,
                "trade_count": m.trade_count,
                "total_pnl": m.total_pnl,
                "avg_pnl": m.avg_pnl,
                "win_rate": m.win_rate,
                "profit_factor": m.profit_factor,
                "expectancy": m.expectancy,
                "avg_return_fraction": m.avg_return_fraction,
                "gross_profit": m.gross_profit,
                "gross_loss": m.gross_loss,
                "per_contract_total_pnl": float(ppc.sum()) if len(ppc) else None,
                "per_contract_avg_pnl": float(ppc.mean()) if len(ppc) else None,
                "total_capital_deployed": float(capital.sum()) if len(capital) else None,
                "max_consecutive_losses": m.max_consecutive_losses,
            }
        )
    result = pd.DataFrame.from_records(records)
    if result.empty:
        return result
    return result.sort_values("total_pnl", ascending=False).reset_index(drop=True)


def compare_groups(df: pd.DataFrame, by: str, values: list[object]) -> pd.DataFrame:
    """Side-by-side comparison restricted to chosen group values
    (e.g. target_delta in [0.50, 0.60, 0.65])."""
    table = grouped_metrics(df, by)
    if table.empty:
        return table
    return table[table["group"].isin(values)].reset_index(drop=True)
