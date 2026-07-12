"""Trade explorer: filterable table with CSV export."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from wolf_trading_os.dashboard.data import cached_trades

_DISPLAY_COLUMNS = [
    "opened_at",
    "closed_at",
    "bot_name",
    "strategy_family",
    "underlying_symbol",
    "instrument_type",
    "status",
    "quantity",
    "target_delta",
    "dte_setting",
    "dte_at_entry",
    "timeframe",
    "premium",
    "risk",
    "realized_pnl",
    "return_pct",
    "return_on_risk",
    "mfe_pct",
    "mae_pct",
    "environment",
    "tags",
]


def _multiselect_filter(
    df: pd.DataFrame, column: str, label: str, container: st.delta_generator.DeltaGenerator
) -> pd.DataFrame:
    options = sorted(v for v in df[column].dropna().unique())
    selected = container.multiselect(label, options)
    if selected:
        df = df[df[column].isin(selected)]
    return df


def render() -> None:
    st.header("Trade explorer")
    df = cached_trades()
    if df.empty:
        st.info("No trades imported yet.")
        return

    with st.expander("Filters", expanded=True):
        row1 = st.columns(4)
        df = _multiselect_filter(df, "bot_name", "Bot", row1[0])
        df = _multiselect_filter(df, "strategy_family", "Strategy family", row1[1])
        df = _multiselect_filter(df, "underlying_symbol", "Symbol", row1[2])
        df = _multiselect_filter(df, "timeframe", "Timeframe", row1[3])

        row2 = st.columns(4)
        df = _multiselect_filter(df, "target_delta", "Target delta", row2[0])
        df = _multiselect_filter(df, "dte_setting", "DTE setting", row2[1])
        df = _multiselect_filter(df, "quantity", "Quantity", row2[2])

        outcome = row2[3].selectbox("Outcome", ["All", "Winners", "Losers", "Flat"])
        if outcome != "All" and "realized_pnl" in df.columns:
            pnl = df["realized_pnl"]
            mask = {
                "Winners": pnl > 0,
                "Losers": pnl < 0,
                "Flat": pnl == 0,
            }[outcome]
            df = df[mask.fillna(False)]

        row3 = st.columns([1, 1, 2])
        min_date = pd.to_datetime(df["opened_at"]).min()
        max_date = pd.to_datetime(df["opened_at"]).max()
        if pd.notna(min_date) and pd.notna(max_date):
            start = row3[0].date_input("From", min_date.date())
            end = row3[1].date_input("To", max_date.date())
            opened = pd.to_datetime(df["opened_at"])
            df = df[
                (opened >= pd.Timestamp(start))
                & (opened < pd.Timestamp(end) + dt.timedelta(days=1))
            ]

        all_tags = sorted({t for tags in df["tags"].dropna() for t in tags})
        chosen_tags = row3[2].multiselect("Tags", all_tags)
        if chosen_tags:
            df = df[df["tags"].map(lambda ts: bool(set(ts or []) & set(chosen_tags)))]

    shown = df[[c for c in _DISPLAY_COLUMNS if c in df.columns]].sort_values(
        "opened_at", ascending=False
    )
    st.caption(f"{len(shown)} trades match the current filters")
    st.dataframe(shown, use_container_width=True, height=480)

    st.download_button(
        "Export filtered trades as CSV",
        shown.to_csv(index=False).encode("utf-8"),
        file_name="wolf-trading-os-trades.csv",
        mime="text/csv",
    )
