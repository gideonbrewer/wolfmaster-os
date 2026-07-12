"""Visualizations page: curves, distributions, breakdowns, comparisons."""

from __future__ import annotations

import streamlit as st

from wolf_trading_os.analytics import closed_trades, equity_curve, grouped_metrics
from wolf_trading_os.analytics.normalization import per_contract_pnl
from wolf_trading_os.dashboard import charts
from wolf_trading_os.dashboard.data import cached_trades

_DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def render() -> None:
    st.header("Visualizations")
    df = cached_trades()
    closed = closed_trades(df)
    if closed.empty:
        st.info("No closed trades to visualize yet.")
        return

    eq = equity_curve(closed)

    tab_curves, tab_breakdowns, tab_excursion, tab_timing, tab_compare = st.tabs(
        ["Equity & drawdown", "Breakdowns", "MFE / MAE", "Timing", "Comparisons"]
    )

    with tab_curves:
        st.plotly_chart(charts.equity_curve_chart(eq.curve), use_container_width=True)
        st.plotly_chart(charts.drawdown_chart(eq.curve), use_container_width=True)
        st.plotly_chart(
            charts.histogram_chart(
                closed["return_fraction"].dropna() * 100, "Return distribution", "Return (%)"
            ),
            use_container_width=True,
        )

    with tab_breakdowns:
        col1, col2 = st.columns(2)
        by_strategy = grouped_metrics(closed, "strategy_family")
        by_symbol = grouped_metrics(closed, "underlying_symbol")
        with col1:
            st.plotly_chart(
                charts.bar_chart(
                    by_strategy, "group", "total_pnl", "P&L by strategy family", "P&L ($)"
                ),
                use_container_width=True,
            )
            pf = (
                by_strategy.dropna(subset=["profit_factor"])
                if not by_strategy.empty
                else (by_strategy)
            )
            st.plotly_chart(
                charts.bar_chart(
                    pf,
                    "group",
                    "profit_factor",
                    "Profit factor by strategy family",
                    "Profit factor",
                    polarity=False,
                ),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                charts.bar_chart(by_symbol, "group", "total_pnl", "P&L by symbol", "P&L ($)"),
                use_container_width=True,
            )
            by_bot = grouped_metrics(closed, "bot_name")
            st.plotly_chart(
                charts.bar_chart(by_bot, "group", "total_pnl", "P&L by bot", "P&L ($)"),
                use_container_width=True,
            )
        st.caption("Table view (accessible alternative to the charts above)")
        st.dataframe(by_strategy, use_container_width=True)

    with tab_excursion:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                charts.excursion_scatter(closed, "mfe_fraction", "MFE vs realized return", "MFE"),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                charts.excursion_scatter(closed, "mae_fraction", "MAE vs realized return", "MAE"),
                use_container_width=True,
            )

    with tab_timing:
        col1, col2 = st.columns(2)
        by_hour = grouped_metrics(closed, "entry_hour")
        by_day = grouped_metrics(closed, "day_of_week")
        if not by_hour.empty:
            by_hour = by_hour.sort_values("group")
        if not by_day.empty:
            by_day["__order"] = by_day["group"].map(_DAY_ORDER.index)
            by_day = by_day.sort_values("__order").drop(columns="__order")
        with col1:
            st.plotly_chart(
                charts.bar_chart(
                    by_hour,
                    "group",
                    "total_pnl",
                    "P&L by entry hour",
                    "P&L ($)",
                    x_title="Entry hour",
                ),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                charts.bar_chart(by_day, "group", "total_pnl", "P&L by day of week", "P&L ($)"),
                use_container_width=True,
            )

    with tab_compare:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                charts.bar_chart(
                    grouped_metrics(closed, "target_delta"),
                    "group",
                    "total_pnl",
                    "P&L by target delta",
                    "P&L ($)",
                    x_title="Target delta (from bot name)",
                ),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                charts.bar_chart(
                    grouped_metrics(closed, "dte_setting"),
                    "group",
                    "total_pnl",
                    "P&L by DTE setting",
                    "P&L ($)",
                    x_title="DTE setting (from bot name)",
                ),
                use_container_width=True,
            )

        st.subheader("Raw vs quantity-normalized P&L by bot")
        st.caption(
            "Left: raw dollars (size-dependent). Right: per-contract dollars "
            "(1-contract equivalent). Separate axes by design — do not compare "
            "bar heights across the two charts."
        )
        by_bot = grouped_metrics(closed, "bot_name")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                charts.bar_chart(by_bot, "group", "total_pnl", "Raw P&L", "P&L ($)"),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                charts.bar_chart(
                    by_bot,
                    "group",
                    "per_contract_total_pnl",
                    "Per-contract P&L",
                    "P&L per contract ($)",
                ),
                use_container_width=True,
            )
        ppc = per_contract_pnl(closed)
        if len(ppc):
            st.plotly_chart(
                charts.histogram_chart(
                    ppc, "Per-contract P&L distribution", "P&L per contract ($)"
                ),
                use_container_width=True,
            )
