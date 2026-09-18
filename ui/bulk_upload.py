"""
'Bulk Upload' tab: upload an Excel file, resolve distances for every row,
download the enriched file.
"""
from __future__ import annotations

import streamlit as st

from src import cost_estimator, excel_io
from src.batch_engine import process_dataframe
from src.cache_store import DistanceCache


def render(api_key: str) -> None:
    st.subheader("Bulk distance calculator")
    st.caption(
        "Upload an Excel file with **source** and **destination** columns "
        "(a **distance** column will be added automatically if it isn't already there)."
    )

    allow_global = st.checkbox(
        "Allow global fallback search",
        value=True,
        help="If a place can't be found within India, search globally instead of marking it Not Found.",
    )

    uploaded = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
    if not uploaded:
        return

    try:
        raw_df = excel_io.read_excel(uploaded)
        df = excel_io.prepare_dataframe(raw_df)
    except excel_io.ExcelValidationError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - surface any read error to the user
        st.error(f"Couldn't read that file: {exc}")
        return

    st.write(f"**{len(df)} rows** loaded.")
    st.dataframe(df.head(10), use_container_width=True)

    unique_pairs = len(df[["source", "destination"]].drop_duplicates())
    est = cost_estimator.estimate(unique_pairs)
    col1, col2, col3 = st.columns(3)
    col1.metric("Rows", len(df))
    col2.metric("Unique pairs", unique_pairs)
    col3.metric(
        "Estimated cost",
        "Within free tier" if est.likely_within_free_tier else f"~${est.estimated_cost_usd}",
    )

    if st.button("Calculate distances", type="primary"):
        cache = DistanceCache()
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def on_progress(progress, message):
            status_text.text(message)
            if progress.total_pairs:
                done = progress.cache_hits + progress.elements_resolved
                progress_bar.progress(min(done / progress.total_pairs, 1.0))

        try:
            with st.spinner("Resolving distances..."):
                result_df = process_dataframe(
                    df,
                    api_key=api_key,
                    allow_global_fallback=allow_global,
                    cache=cache,
                    on_progress=on_progress,
                )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Something went wrong while processing: {exc}")
            return

        progress_bar.progress(1.0)
        st.success("Done.")

        st.dataframe(result_df, use_container_width=True)

        found = int((result_df["status"] != "Not found").sum())
        fallback = int((result_df["status"] == "Found (global fallback)").sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Resolved", f"{found}/{len(result_df)}")
        c2.metric("Used global fallback", fallback)
        c3.metric("Not found", len(result_df) - found)

        st.download_button(
            "Download results as Excel",
            data=excel_io.to_excel_bytes(result_df),
            file_name="distance_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
