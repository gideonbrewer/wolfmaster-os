"""Overview page: headline KPIs, raw vs normalized, excursion summary."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from wolf_trading_os.dashboard.data import trades_or_error
from wolf_trading_os.services import build_analytics_bundle


def _fmt_usd(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def _fmt_num(value: float | None, digits: int = 2) -> str:
    return f"{value:.{digits}f}" if value is not None else "—"


def _fmt_pct_unit(value: float | None, digits: int = 1) -> str:
    """Format a value already expressed in percent points."""
    return f"{value:.{digits}f}%" if value is not None else "—"


def _fmt_fraction(value: float | None, digits: int = 1) -> str:
    """Format a decimal fraction (0.125) as percent points (12.5%)."""
    return f"{value * 100:.{digits}f}%" if value is not None else "—"


def render() -> None:
    st.header("Overview")
    df = trades_or_error()
    if df is None:
        return
    if df.empty:
        st.info("No trades imported yet. Use the **Import** page or the CLI.")
        return

    bundle = build_analytics_bundle(df)
    core, norm, eq, exc = bundle.core, bundle.normalized, bundle.equity, bundle.excursion

    open_count = len(df) - core.trade_count
    date_lo = pd.to_datetime(df["opened_at"]).min()
    date_hi = pd.to_datetime(df["opened_at"]).max()

    row1 = st.columns(5)
    row1[0].metric("Total P&L (raw $)", _fmt_usd(core.total_pnl))
    row1[1].metric(
        "Closed trades",
        f"{core.trade_count}",
        help=f"{open_count} open/unresolved trades are excluded from performance metrics",
    )
    row1[2].metric(
        "Win rate",
        _fmt_pct_unit(core.win_rate * 100) if core.win_rate is not None else "—",
    )
    row1[3].metric("Profit factor", _fmt_num(core.profit_factor))
    row1[4].metric("Expectancy / trade", _fmt_usd(core.expectancy))

    row2 = st.columns(5)
    row2[0].metric("Max drawdown", _fmt_usd(eq.max_drawdown))
    row2[1].metric("Avg MFE", _fmt_fraction(exc.avg_mfe_fraction))
    row2[2].metric(
        "MFE capture ratio",
        _fmt_num(exc.mfe_capture_ratio),
        help="mean(realized return) / mean(MFE) over trades with positive MFE",
    )
    row2[3].metric("Avg MAE", _fmt_fraction(exc.avg_mae_fraction))
    with row2[4]:
        st.metric("Open trades excluded", str(open_count))
        if pd.notna(date_lo):
            st.caption(f"Imported range: {date_lo:%Y-%m-%d} → {date_hi:%Y-%m-%d}")

    st.divider()
    st.subheader("Raw dollars vs quantity-normalized")
    st.caption(
        "Raw P&L depends on position size. Per-contract and per-$1,000-deployed "
        "figures measure strategy quality independent of sizing — the two are "
        "not interchangeable."
    )
    cols = st.columns(4)
    cols[0].metric("Raw total P&L", _fmt_usd(norm.raw_total_pnl))
    cols[1].metric("Per-contract total P&L", _fmt_usd(norm.per_contract_total_pnl))
    cols[2].metric("P&L per $1k deployed", _fmt_usd(norm.pnl_per_1k_deployed))
    cols[3].metric(
        "Equal-weighted avg return",
        _fmt_fraction(norm.equal_weighted_avg_return_fraction),
    )

    st.divider()
    st.subheader("Streaks and extremes")
    cols = st.columns(4)
    cols[0].metric("Best trade", _fmt_usd(core.best_trade_pnl))
    cols[1].metric("Worst trade", _fmt_usd(core.worst_trade_pnl))
    cols[2].metric("Max consecutive wins", str(core.max_consecutive_wins))
    cols[3].metric("Max consecutive losses", str(core.max_consecutive_losses))
