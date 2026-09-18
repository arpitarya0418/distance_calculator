"""
'Test' tab: manual source/destination lookup with autocomplete suggestions
and a distance+time comparison across walk / drive / bicycle.
"""
from __future__ import annotations

import uuid

import streamlit as st

from src import maps_client

MODES = [("DRIVE", "Car", "\U0001F697"), ("WALK", "Walk", "\U0001F6B6")]


def _suggest(query: str, api_key: str, session_token: str) -> list[str]:
    if not query or len(query) < 3:
        return []
    try:
        results = maps_client.autocomplete(query, api_key, session_token=session_token)
    except maps_client.MapsAPIError:
        return []
    return [r["text"] for r in results]


def render(api_key: str) -> None:
    st.subheader("Test a single route")
    st.caption("Search for a source and destination and compare car, walk, and bicycle routes.")

    if "ac_session_token" not in st.session_state:
        st.session_state.ac_session_token = str(uuid.uuid4())

    try:
        from streamlit_searchbox import st_searchbox
    except ImportError:
        st.error(
            "The `streamlit-searchbox` package isn't installed. "
            "It's in requirements.txt - run `pip install -r requirements.txt` again."
        )
        return

    col1, col2 = st.columns(2)
    with col1:
        source = st_searchbox(
            lambda q: _suggest(q, api_key, st.session_state.ac_session_token),
            key="source_searchbox",
            placeholder="Source, e.g. Bandra Kurla Complex, Mumbai",
        )
    with col2:
        destination = st_searchbox(
            lambda q: _suggest(q, api_key, st.session_state.ac_session_token),
            key="destination_searchbox",
            placeholder="Destination, e.g. Pune Station",
        )

    if not source or not destination:
        st.info("Pick a source and destination above to compare routes.")
        return

    if st.button("Compare routes", type="primary"):
        with st.spinner("Resolving locations..."):
            origin_place = maps_client.geocode(source, api_key, region="in") or maps_client.geocode(source, api_key, region=None)
            dest_place = maps_client.geocode(destination, api_key, region="in") or maps_client.geocode(destination, api_key, region=None)

        if not origin_place or not dest_place:
            st.error("Couldn't resolve one of those locations. Try a more specific search.")
            return

        # Fresh session token for the next search (Google's autocomplete session-token pattern).
        st.session_state.ac_session_token = str(uuid.uuid4())

        cols = st.columns(3)
        for (mode, label, emoji), col in zip(MODES, cols):
            with col:
                with st.spinner(f"{label}..."):
                    try:
                        route = maps_client.compute_route(
                            (origin_place["lat"], origin_place["lng"]),
                            (dest_place["lat"], dest_place["lng"]),
                            api_key=api_key,
                            travel_mode=mode,
                        )
                    except maps_client.MapsAPIError as exc:
                        st.error(f"{emoji} {label}: {exc}")
                        continue
                if route is None:
                    st.warning(f"{emoji} {label}: No route found")
                else:
                    st.metric(
                        f"{emoji} {label}",
                        f"{route['distance_m'] / 1000:.1f} km",
                        f"{route['duration_s'] / 60:.0f} min",
                    )
