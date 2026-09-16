import streamlit as st
from services.geocoder import search_places
from services.router import calculate_route
from utils.formatting import format_distance, format_duration

st.set_page_config(
    page_title="Distance Calculator",
    page_icon="📍",
    layout="wide"
)

# ==============================
# THEME / CSS
# ==============================

st.markdown("""
<style>
/* Main application */
.stApp {
    background: #0f172a !important;
}

/* Main content */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px !important;
}

/* Main title */
.app-title {
    color: #ffffff !important;
    font-size: 38px !important;
    font-weight: 700 !important;
    margin-bottom: 4px !important;
}

/* Subtitle */
.app-subtitle {
    color: #cbd5e1 !important;
    font-size: 17px !important;
    margin-bottom: 30px !important;
}

/* Section headings */
.section-title {
    color: #ffffff !important;
    font-size: 20px !important;
    font-weight: 700 !important;
    margin-bottom: 10px !important;
}

.route-heading {
    color: #ffffff !important;
    font-size: 24px !important;
    font-weight: 700 !important;
    margin-bottom: 15px !important;
}

.locations-heading {
    color: #ffffff !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    margin-top: 20px !important;
    margin-bottom: 12px !important;
}

/* ==============================
   INPUT BOXES
   ============================== */

div[data-baseweb="input"] {
    background-color: #ffffff !important;
    border-radius: 8px !important;
}

div[data-baseweb="input"] > div {
    background-color: #ffffff !important;
}

div[data-baseweb="input"] input {
    color: #111827 !important;
    background-color: #ffffff !important;
    -webkit-text-fill-color: #111827 !important;
}

div[data-baseweb="input"] input::placeholder {
    color: #6b7280 !important;
    -webkit-text-fill-color: #6b7280 !important;
    opacity: 1 !important;
}

/* ==============================
   SELECT BOX
   ============================== */

div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border-radius: 8px !important;
}

div[data-baseweb="select"] span {
    color: #111827 !important;
}

div[data-baseweb="select"] svg {
    fill: #111827 !important;
}

/* Dropdown options */
div[role="listbox"] {
    background-color: #ffffff !important;
}

div[role="option"] {
    background-color: #ffffff !important;
    color: #111827 !important;
}

div[role="option"] * {
    color: #111827 !important;
}

/* ==============================
   RESULT CARD
   ============================== */

.result-card {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    padding: 20px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
}

.result-title {
    color: #111827 !important;
    font-size: 20px !important;
    font-weight: 700 !important;
    margin-bottom: 16px !important;
}

.result-label {
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
}

.result-value {
    color: #111827 !important;
    font-size: 24px !important;
    font-weight: 700 !important;
    margin-top: 3px !important;
}

/* ==============================
   LOCATION CARD
   ============================== */

.location-card {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    padding: 20px !important;
    margin-bottom: 14px !important;
}

.location-text {
    color: #111827 !important;
    font-size: 15px !important;
    margin-bottom: 8px !important;
}

.location-text b {
    color: #111827 !important;
}

/* ==============================
   READY CARD
   ============================== */

.ready-card {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    padding: 55px 20px !important;
    text-align: center !important;
}

.ready-title {
    color: #111827 !important;
    font-size: 22px !important;
    font-weight: 700 !important;
}

.ready-text {
    color: #64748b !important;
    font-size: 15px !important;
}

/* ==============================
   BUTTON
   ============================== */

.stButton > button {
    border-radius: 8px !important;
    font-weight: 700 !important;
}

/* ==============================
   WARNINGS / ERRORS
   ============================== */

div[data-testid="stAlert"] {
    border-radius: 8px !important;
}

/* ==============================
   FOOTER
   ============================== */

.footer {
    color: #94a3b8 !important;
    text-align: center !important;
    font-size: 13px !important;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# HEADER
# ==============================

st.markdown(
    '<div class="app-title">📍 Distance Calculator</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="app-subtitle">'
    'Compare distance and estimated travel time between two locations.'
    '</div>',
    unsafe_allow_html=True
)

# ==============================
# SESSION STATE
# ==============================

if "source_results" not in st.session_state:
    st.session_state.source_results = []

if "destination_results" not in st.session_state:
    st.session_state.destination_results = []

# ==============================
# MAIN LAYOUT
# ==============================

left, right = st.columns([1, 2], gap="large")

# ============================================================
# LEFT SIDE
# ============================================================

with left:

    st.markdown(
        '<div class="section-title">📍 Source</div>',
        unsafe_allow_html=True
    )

    source_query = st.text_input(
        "Search source",
        placeholder="City, airport, landmark or address",
        label_visibility="collapsed",
        key="source_query"
    )

    if source_query and len(source_query.strip()) >= 3:
        try:
            st.session_state.source_results = search_places(
                source_query.strip()
            )
        except Exception as e:
            st.error(f"Search failed: {e}")

    source_options = st.session_state.source_results
    source = None

    if source_options:

        source_index = st.selectbox(
            "Select source",
            range(len(source_options)),
            format_func=lambda i: source_options[i]["name"],
            key="source_selection"
        )

        source = source_options[source_index]

    st.markdown(
        '<div style="height:25px;"></div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="section-title">🏁 Destination</div>',
        unsafe_allow_html=True
    )

    destination_query = st.text_input(
        "Search destination",
        placeholder="City, airport, landmark or address",
        label_visibility="collapsed",
        key="destination_query"
    )

    if destination_query and len(destination_query.strip()) >= 3:
        try:
            st.session_state.destination_results = search_places(
                destination_query.strip()
            )
        except Exception as e:
            st.error(f"Search failed: {e}")

    destination_options = st.session_state.destination_results
    destination = None

    if destination_options:

        destination_index = st.selectbox(
            "Select destination",
            range(len(destination_options)),
            format_func=lambda i: destination_options[i]["name"],
            key="destination_selection"
        )

        destination = destination_options[destination_index]

    st.markdown(
        '<div style="height:25px;"></div>',
        unsafe_allow_html=True
    )

    calculate = st.button(
        "🚀 Calculate Route",
        type="primary",
        use_container_width=True
    )

# ============================================================
# RIGHT SIDE
# ============================================================

with right:

    st.markdown(
        '<div class="route-heading">Route Results</div>',
        unsafe_allow_html=True
    )

    if calculate:

        if not source:
            st.warning("Please select a source.")
            st.stop()

        if not destination:
            st.warning("Please select a destination.")
            st.stop()

        if (
            source["latitude"] == destination["latitude"]
            and source["longitude"] == destination["longitude"]
        ):
            st.warning("Source and destination cannot be the same.")
            st.stop()

        modes = [
            ("🚗", "Car"),
            ("🚲", "Bicycle"),
            ("🚶", "Walking")
        ]

        results = []

        with st.spinner("Calculating routes..."):

            for icon, mode in modes:

                try:

                    result = calculate_route(
                        source["latitude"],
                        source["longitude"],
                        destination["latitude"],
                        destination["longitude"],
                        mode
                    )

                    results.append({
                        "icon": icon,
                        "mode": mode,
                        "distance": format_distance(
                            result["distance_km"]
                        ),
                        "duration": format_duration(
                            result["duration_minutes"]
                        ),
                        "error": None
                    })

                except Exception as e:

                    results.append({
                        "icon": icon,
                        "mode": mode,
                        "distance": "Unavailable",
                        "duration": "Unavailable",
                        "error": str(e)
                    })

        # ====================================================
        # ROUTE RESULT CARDS
        # ====================================================

        for result in results:

            with st.container():

                st.markdown(
                    '<div class="result-card">',
                    unsafe_allow_html=True
                )

                st.markdown(
                    f'<div class="result-title">'
                    f'{result["icon"]} {result["mode"]}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                col1, col2 = st.columns(2)

                with col1:

                    st.markdown(
                        '<div class="result-label">'
                        'DISTANCE'
                        '</div>',
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        f'<div class="result-value">'
                        f'{result["distance"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                with col2:

                    st.markdown(
                        '<div class="result-label">'
                        'ESTIMATED TIME'
                        '</div>',
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        f'<div class="result-value">'
                        f'{result["duration"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                st.markdown(
                    '</div>',
                    unsafe_allow_html=True
                )

            if result["error"]:

                st.caption(
                    f'{result["mode"]} route unavailable.'
                )

        # ====================================================
        # SELECTED LOCATIONS
        # ====================================================

        st.markdown(
            '<div class="locations-heading">'
            '📌 Selected Locations'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="location-card">',
            unsafe_allow_html=True
        )

        st.markdown(
            f'<div class="location-text">'
            f'<b>From:</b> {source["name"]}'
            f'</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            f'<div class="location-text">'
            f'<b>To:</b> {destination["name"]}'
            f'</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )

    else:

        st.markdown(
            """
            <div class="ready-card">

                <div style="font-size:48px;">
                    🗺️
                </div>

                <div class="ready-title">
                    Ready to calculate
                </div>

                <p class="ready-text">
                    Select your source and destination,
                    then click <b>Calculate Route</b>.
                </p>

            </div>
            """,
            unsafe_allow_html=True
        )

# ==============================
# FOOTER
# ==============================

st.divider()

st.markdown(
    '<div class="footer">'
    'Routing powered by OpenStreetMap / OSRM.'
    '</div>',
    unsafe_allow_html=True
)
