"""MFE / MAE (excursion) analysis.

MFE% and MAE% come from Option Alpha's highReturnPct / lowReturnPct
columns (percent units, same base as return_pct). Intratrade excursion is
NOT reconstructed from market data in Phase 1.

Formulas in docs/analytics-definitions.md. Key definitions:
- MFE capture ratio (aggregate) = mean(return_pct) / mean(mfe_pct) over
  trades with mfe_pct > 0. The aggregate form is used because per-trade
  ratios explode when mfe_pct is near zero; the median of per-trade
  ratios is reported as a robust secondary view.
- Profit giveback (per trade)   = mfe_pct - return_pct, for mfe_pct > 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

MFE_THRESHOLDS: tuple[float, ...] = (5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 50.0)
ADVERSE_THRESHOLDS: tuple[float, ...] = (5.0, 10.0, 20.0, 30.0, 50.0)
_GIVEBACK_THRESHOLD = 5.0  # "reached a positive threshold" = MFE >= +5%


@dataclass(frozen=True, slots=True)
class ExcursionStats:
    trades_with_mfe: int
    trades_with_mae: int
    avg_mfe_pct: float | None
    median_mfe_pct: float | None
    avg_mae_pct: float | None
    median_mae_pct: float | None
    mfe_capture_ratio: float | None  # mean(return) / mean(mfe), mfe > 0
    median_trade_capture_ratio: float | None  # median of per-trade return/mfe
    avg_profit_giveback_pct: float | None  # mean of (mfe - return), mfe > 0
    # trades whose MFE reached each threshold: {5.0: n, 10.0: n, ...}
    reached_threshold: dict[float, int] = field(default_factory=dict)
    # reached >= +5% MFE but closed...
    reached_but_closed_flat: int = 0
    reached_but_closed_below_5pct: int = 0  # 0 < return < 5
    reached_but_closed_negative: int = 0
    losers_previously_profitable: int = 0  # pnl < 0 and mfe_pct > 0
    # winners whose MAE breached each adverse threshold: {5.0: n, ...}
    winners_with_adverse_excursion: dict[float, int] = field(default_factory=dict)


def excursion_stats(df: pd.DataFrame) -> ExcursionStats:
    cols = df.columns
    mfe = df["mfe_pct"].dropna() if "mfe_pct" in cols else pd.Series(dtype=float)
    mae = df["mae_pct"].dropna() if "mae_pct" in cols else pd.Series(dtype=float)

    # Capture/giveback need both MFE and realized return.
    if "mfe_pct" in cols and "return_pct" in cols:
        both = df[["mfe_pct", "return_pct"]].dropna()
        pos = both[both["mfe_pct"] > 0]
        capture = (pos["return_pct"] / pos["mfe_pct"]).astype(float)
        giveback = (pos["mfe_pct"] - pos["return_pct"]).astype(float)
    else:
        pos = pd.DataFrame(columns=["mfe_pct", "return_pct"])
        capture = pd.Series(dtype=float)
        giveback = pd.Series(dtype=float)

    reached = {t: int((mfe >= t).sum()) for t in MFE_THRESHOLDS}

    reached_5 = pos[pos["mfe_pct"] >= _GIVEBACK_THRESHOLD]
    closed_flat = int((reached_5["return_pct"] == 0).sum())
    closed_below = int(
        ((reached_5["return_pct"] > 0) & (reached_5["return_pct"] < _GIVEBACK_THRESHOLD)).sum()
    )
    closed_negative = int((reached_5["return_pct"] < 0).sum())

    losers_prev_profitable = 0
    winners_adverse: dict[float, int] = dict.fromkeys(ADVERSE_THRESHOLDS, 0)
    if "realized_pnl" in cols:
        if "mfe_pct" in cols:
            lp = df[["realized_pnl", "mfe_pct"]].dropna()
            losers_prev_profitable = int(((lp["realized_pnl"] < 0) & (lp["mfe_pct"] > 0)).sum())
        if "mae_pct" in cols:
            wm = df[["realized_pnl", "mae_pct"]].dropna()
            winners = wm[wm["realized_pnl"] > 0]
            winners_adverse = {t: int((winners["mae_pct"] <= -t).sum()) for t in ADVERSE_THRESHOLDS}

    return ExcursionStats(
        trades_with_mfe=len(mfe),
        trades_with_mae=len(mae),
        avg_mfe_pct=float(mfe.mean()) if len(mfe) else None,
        median_mfe_pct=float(mfe.median()) if len(mfe) else None,
        avg_mae_pct=float(mae.mean()) if len(mae) else None,
        median_mae_pct=float(mae.median()) if len(mae) else None,
        mfe_capture_ratio=(
            float(pos["return_pct"].mean() / pos["mfe_pct"].mean())
            if len(pos) and pos["mfe_pct"].mean() != 0
            else None
        ),
        median_trade_capture_ratio=float(capture.median()) if len(capture) else None,
        avg_profit_giveback_pct=float(giveback.mean()) if len(giveback) else None,
        reached_threshold=reached,
        reached_but_closed_flat=closed_flat,
        reached_but_closed_below_5pct=closed_below,
        reached_but_closed_negative=closed_negative,
        losers_previously_profitable=losers_prev_profitable,
        winners_with_adverse_excursion=winners_adverse,
    )
