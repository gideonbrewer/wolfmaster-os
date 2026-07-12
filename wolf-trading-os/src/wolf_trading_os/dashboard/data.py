"""Cached data access for the dashboard with sanitized failure handling."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from wolf_trading_os.services import load_trades_safely


@st.cache_data(ttl=60, show_spinner="Loading trades…")
def _cached_load() -> tuple[pd.DataFrame | None, str | None]:
    return load_trades_safely()


def invalidate_trades_cache() -> None:
    _cached_load.clear()


def trades_or_error() -> pd.DataFrame | None:
    """Return the trades DataFrame, or render a sanitized error with a
    retry control and return None. Never exposes URLs, credentials, or
    stack traces (audit item 15)."""
    df, error = _cached_load()
    if error is not None:
        st.error(error)
        if st.button("Retry"):
            invalidate_trades_cache()
            st.rerun()
        return None
    return df
