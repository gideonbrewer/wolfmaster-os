"""Streamlit dashboard entry point.

Run via `wolf-trading-os run-dashboard` or
`streamlit run src/wolf_trading_os/dashboard/app.py`.
"""

from __future__ import annotations

import streamlit as st

from wolf_trading_os.dashboard.sections import explorer, importer, overview, visualizations
from wolf_trading_os.logging import configure_logging

configure_logging()

st.set_page_config(
    page_title="Wolf Trading OS",
    page_icon="🐺",
    layout="wide",
)

PAGES = {
    "Overview": overview.render,
    "Visualizations": visualizations.render,
    "Trade explorer": explorer.render,
    "Import": importer.render,
}

with st.sidebar:
    st.title("🐺 Wolf Trading OS")
    st.caption("Phase 1 — analytics only. No order capability, no broker connections.")
    page = st.radio("Section", list(PAGES), label_visibility="collapsed")

PAGES[page]()
