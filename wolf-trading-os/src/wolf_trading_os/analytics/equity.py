"""Equity curve and drawdown analysis.

The equity curve is cumulative realized P&L in close-time order (fallback
open time), starting from zero — Phase 1 has no account-balance data.
Percentage drawdown is only reported where the running peak is positive;
otherwise it is mathematically meaningless and stays None (fail closed).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class EquityStats:
    curve: pd.DataFrame  # columns: ts, equity, peak, drawdown, drawdown_pct
    max_drawdown: float  # dollars, >= 0
    max_drawdown_pct: float | None  # percent, only where peak > 0
    max_drawdown_duration_days: float | None  # peak -> trough
    recovery_duration_days: float | None  # trough -> recovery; None if unrecovered


def equity_curve(df: pd.DataFrame) -> EquityStats:
    sub = df[df["realized_pnl"].notna()] if "realized_pnl" in df.columns else df.iloc[0:0]
    if sub.empty:
        empty = pd.DataFrame(columns=["ts", "equity", "peak", "drawdown", "drawdown_pct"])
        return EquityStats(empty, 0.0, None, None, None)

    ts = (
        sub["closed_at"].fillna(sub["opened_at"])
        if "closed_at" in sub.columns
        else (sub["opened_at"])
    )
    ordered_index = ts.sort_values(kind="stable").index
    pnl = sub.loc[ordered_index, "realized_pnl"].astype(float)
    ts = ts.loc[ordered_index]

    equity = pnl.cumsum()
    # The account starts at equity 0 before the first trade, so the running
    # peak is never below 0 — an immediately negative curve is a drawdown.
    peak = equity.cummax().clip(lower=0.0)
    drawdown = peak - equity  # >= 0
    drawdown_pct = pd.Series(
        [(dd / p * 100.0) if p > 0 else None for dd, p in zip(drawdown, peak, strict=True)],
        index=equity.index,
        dtype=object,
    )

    curve = pd.DataFrame(
        {
            "ts": ts.to_numpy(),
            "equity": equity.to_numpy(),
            "peak": peak.to_numpy(),
            "drawdown": drawdown.to_numpy(),
            "drawdown_pct": drawdown_pct.to_numpy(),
        }
    ).reset_index(drop=True)

    max_dd = float(drawdown.max())
    valid_pct = [v for v in drawdown_pct if v is not None]
    max_dd_pct = float(max(valid_pct)) if valid_pct else None

    dd_duration, recovery_duration = _drawdown_durations(curve)

    return EquityStats(
        curve=curve,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_duration_days=dd_duration,
        recovery_duration_days=recovery_duration,
    )


def _drawdown_durations(curve: pd.DataFrame) -> tuple[float | None, float | None]:
    """Durations for the MAXIMUM drawdown episode.

    Drawdown duration: time from the peak preceding the maximum drawdown
    trough to that trough. Recovery duration: trough to the first point
    where equity regains the prior peak (None while unrecovered).
    """
    if curve.empty or curve["drawdown"].max() <= 0:
        return None, None

    trough_pos = int(curve["drawdown"].idxmax())
    trough_ts = curve.loc[trough_pos, "ts"]
    peak_value = curve.loc[trough_pos, "peak"]

    pre = curve.iloc[: trough_pos + 1]
    peak_rows = pre[pre["equity"] >= peak_value]
    dd_duration: float | None = None
    if not peak_rows.empty:
        peak_ts = peak_rows.iloc[0]["ts"]
        if pd.notna(peak_ts) and pd.notna(trough_ts):
            dd_duration = (trough_ts - peak_ts).total_seconds() / 86400.0

    post = curve.iloc[trough_pos + 1 :]
    recovered = post[post["equity"] >= peak_value]
    recovery_duration: float | None = None
    if not recovered.empty:
        rec_ts = recovered.iloc[0]["ts"]
        if pd.notna(rec_ts) and pd.notna(trough_ts):
            recovery_duration = (rec_ts - trough_ts).total_seconds() / 86400.0

    return dd_duration, recovery_duration
