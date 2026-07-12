"""Cached data access for the dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from wolf_trading_os.analytics import load_trades


@st.cache_data(ttl=60, show_spinner="Loading trades…")
def cached_trades() -> pd.DataFrame:
    return load_trades()


def invalidate_trades_cache() -> None:
    cached_trades.clear()
