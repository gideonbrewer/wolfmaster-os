"""MFE / MAE (excursion) analysis.

MFE and MAE come from Option Alpha's highReturnPct / lowReturnPct
columns, stored as DECIMAL FRACTIONS (0.05 == +5%), same base as
return_fraction. Intratrade excursion is NOT reconstructed from market
data in Phase 1.

Formulas in docs/analytics-definitions.md. Key definitions:
- MFE capture ratio (aggregate) = mean(return_fraction) / mean(mfe_fraction) over
  trades with mfe_fraction > 0. The aggregate form is used because per-trade
  ratios explode when mfe_fraction is near zero; the median of per-trade
  ratios is reported as a robust secondary view.
- Profit giveback (per trade)   = mfe_fraction - return_fraction, for mfe_fraction > 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

MFE_THRESHOLDS: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.50)
ADVERSE_THRESHOLDS: tuple[float, ...] = (0.05, 0.10, 0.20, 0.30, 0.50)
_GIVEBACK_THRESHOLD = 0.05  # "reached a positive threshold" = MFE >= +5%


@dataclass(frozen=True, slots=True)
class ExcursionStats:
    trades_with_mfe: int
    trades_with_mae: int
    avg_mfe_fraction: float | None
    median_mfe_fraction: float | None
    avg_mae_fraction: float | None
    median_mae_fraction: float | None
    mfe_capture_ratio: float | None  # mean(return) / mean(mfe), mfe > 0
    median_trade_capture_ratio: float | None  # median of per-trade return/mfe
    avg_profit_giveback_fraction: float | None  # mean of (mfe - return), mfe > 0
    # trades whose MFE reached each threshold: {5.0: n, 10.0: n, ...}
    reached_threshold: dict[float, int] = field(default_factory=dict)
    # reached >= +5% MFE but closed...
    reached_but_closed_flat: int = 0
    reached_but_closed_below_5pct: int = 0  # 0 < return_fraction < 0.05
    reached_but_closed_negative: int = 0
    losers_previously_profitable: int = 0  # pnl < 0 and mfe_fraction > 0
    # winners whose MAE breached each adverse threshold: {5.0: n, ...}
    winners_with_adverse_excursion: dict[float, int] = field(default_factory=dict)


def excursion_stats(df: pd.DataFrame) -> ExcursionStats:
    cols = df.columns
    mfe = df["mfe_fraction"].dropna() if "mfe_fraction" in cols else pd.Series(dtype=float)
    mae = df["mae_fraction"].dropna() if "mae_fraction" in cols else pd.Series(dtype=float)

    # Capture/giveback need both MFE and realized return.
    if "mfe_fraction" in cols and "return_fraction" in cols:
        both = df[["mfe_fraction", "return_fraction"]].dropna()
        pos = both[both["mfe_fraction"] > 0]
        capture = (pos["return_fraction"] / pos["mfe_fraction"]).astype(float)
        giveback = (pos["mfe_fraction"] - pos["return_fraction"]).astype(float)
    else:
        pos = pd.DataFrame(columns=["mfe_fraction", "return_fraction"])
        capture = pd.Series(dtype=float)
        giveback = pd.Series(dtype=float)

    reached = {t: int((mfe >= t).sum()) for t in MFE_THRESHOLDS}

    reached_5 = pos[pos["mfe_fraction"] >= _GIVEBACK_THRESHOLD]
    closed_flat = int((reached_5["return_fraction"] == 0).sum())
    closed_below = int(
        (
            (reached_5["return_fraction"] > 0)
            & (reached_5["return_fraction"] < _GIVEBACK_THRESHOLD)
        ).sum()
    )
    closed_negative = int((reached_5["return_fraction"] < 0).sum())

    losers_prev_profitable = 0
    winners_adverse: dict[float, int] = dict.fromkeys(ADVERSE_THRESHOLDS, 0)
    if "realized_pnl" in cols:
        if "mfe_fraction" in cols:
            lp = df[["realized_pnl", "mfe_fraction"]].dropna()
            losers_prev_profitable = int(
                ((lp["realized_pnl"] < 0) & (lp["mfe_fraction"] > 0)).sum()
            )
        if "mae_fraction" in cols:
            wm = df[["realized_pnl", "mae_fraction"]].dropna()
            winners = wm[wm["realized_pnl"] > 0]
            winners_adverse = {
                t: int((winners["mae_fraction"] <= -t).sum()) for t in ADVERSE_THRESHOLDS
            }

    return ExcursionStats(
        trades_with_mfe=len(mfe),
        trades_with_mae=len(mae),
        avg_mfe_fraction=float(mfe.mean()) if len(mfe) else None,
        median_mfe_fraction=float(mfe.median()) if len(mfe) else None,
        avg_mae_fraction=float(mae.mean()) if len(mae) else None,
        median_mae_fraction=float(mae.median()) if len(mae) else None,
        mfe_capture_ratio=(
            float(pos["return_fraction"].mean() / pos["mfe_fraction"].mean())
            if len(pos) and pos["mfe_fraction"].mean() != 0
            else None
        ),
        median_trade_capture_ratio=float(capture.median()) if len(capture) else None,
        avg_profit_giveback_fraction=float(giveback.mean()) if len(giveback) else None,
        reached_threshold=reached,
        reached_but_closed_flat=closed_flat,
        reached_but_closed_below_5pct=closed_below,
        reached_but_closed_negative=closed_negative,
        losers_previously_profitable=losers_prev_profitable,
        winners_with_adverse_excursion=winners_adverse,
    )
