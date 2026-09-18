"""
Entry point. Run locally with:
    streamlit run app.py
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from ui import bulk_upload, test_playground

st.set_page_config(page_title="Distance Calculator", page_icon="\U0001F4CD", layout="wide")


def get_api_key() -> Optional[str]:
    if "GOOGLE_MAPS_API_KEY" in st.secrets:
        return st.secrets["GOOGLE_MAPS_API_KEY"]
    return None


def main() -> None:
    st.title("\U0001F4CD Distance Calculator")
    st.caption("Bulk Excel distance lookups and a single-route test tool, powered by Google Maps Platform.")

    api_key = get_api_key()
    if not api_key:
        st.error(
            "No API key found. Add `GOOGLE_MAPS_API_KEY = \"your-key\"` to "
            "`.streamlit/secrets.toml` locally, or to your app's Secrets in "
            "Streamlit Community Cloud."
        )
        st.stop()

    tab_bulk, tab_test = st.tabs(["\U0001F4CA Bulk Upload", "\U0001F9EA Test"])
    with tab_bulk:
        bulk_upload.render(api_key)
    with tab_test:
        test_playground.render(api_key)


if __name__ == "__main__":
    main()
