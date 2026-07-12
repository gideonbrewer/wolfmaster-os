"""Import page: CSV upload with a full validation summary."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from wolf_trading_os.dashboard.data import invalidate_trades_cache
from wolf_trading_os.ingestion.option_alpha import OptionAlphaImporter


def render() -> None:
    st.header("Import Option Alpha CSV")
    st.caption(
        "Upload one or more Option Alpha trade-history exports. Rows are "
        "validated and normalized; malformed rows are reported below without "
        "aborting the import, and re-imports never create duplicates."
    )

    uploads = st.file_uploader("CSV exports", type=["csv"], accept_multiple_files=True)
    if not uploads:
        return
    if not st.button(f"Import {len(uploads)} file(s)", type="primary"):
        return

    importer = OptionAlphaImporter()
    for upload in uploads:
        summary = importer.import_buffer(io.BytesIO(upload.getvalue()), upload.name)
        result = summary.files[0]

        st.subheader(upload.name)
        if not result.ok:
            st.error(f"File rejected: {result.error}")
            continue

        cols = st.columns(4)
        cols[0].metric("Rows received", result.rows_received)
        cols[1].metric("Rows accepted", result.rows_accepted)
        cols[2].metric("Rows rejected", result.rows_rejected)
        cols[3].metric("Duplicates skipped", result.rows_duplicate)

        if result.unknown_columns:
            st.info(f"Ignored unrecognized columns: {', '.join(result.unknown_columns)}")
        if result.rejected_rows:
            st.error(f"{len(result.rejected_rows)} row(s) rejected:")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"row": r.row_number, "problems": "; ".join(r.messages)}
                        for r in result.rejected_rows
                    ]
                ),
                use_container_width=True,
            )
        if result.warnings:
            st.warning(f"{len(result.warnings)} row(s) accepted with warnings:")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"row": w.row_number, "warnings": "; ".join(w.messages)}
                        for w in result.warnings
                    ]
                ),
                use_container_width=True,
            )
        if result.rows_accepted and not result.rejected_rows:
            st.success("Import complete.")

    invalidate_trades_cache()
