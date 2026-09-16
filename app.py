import streamlit as st
from services.geocoder import search_places
from services.router import calculate_route
from utils.formatting import format_distance, format_duration

st.set_page_config(
    page_title="Distance Calculator",
    page_icon="📍",
    layout="wide"
)

# ============================================================
# CSS
# ============================================================

st.html("""
<style>
/* ==============================
   APPLICATION
   ============================== */

.stApp {
    background: #0f172a !important;
}

.block-container {
    max-width: 1200px !important;
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
}

/* ==============================
   TITLE
   ============================== */

.app-title {
    color: #ffffff !important;
    font-size: 38px !important;
    font-weight: 700 !important;
    line-height: 1.4 !important;
    margin: 0 !important;
    padding: 0 !important;
    display: block !important;
    overflow: visible !important;
}

.app-subtitle {
    color: #cbd5e1 !important;
    font-size: 17px !important;
    line-height: 1.5 !important;
    margin-top: 6px !important;
    margin-bottom: 30px !important;
    padding: 0 !important;
}

/* ==============================
   SECTION TITLES
   ============================== */

.section-title {
    color: #ffffff !important;
    font-size: 20px !important;
    font-weight: 700 !important;
    line-height: 1.4 !important;
    margin-bottom: 10px !important;
}

.route-heading {
    color: #ffffff !important;
    font-size: 24px !important;
    font-weight: 700 !important;
    line-height: 1.4 !important;
    margin-bottom: 15px !important;
}

.locations-heading {
    color: #ffffff !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    line-height: 1.4 !important;
    margin-top: 20px !important;
    margin-bottom: 12px !important;
}

/* ==============================
   INPUTS
   ============================== */

div[data-baseweb="input"] {
    background: #ffffff !important;
    border-radius: 8px !important;
}

div[data-baseweb="input"] > div {
    background: #ffffff !important;
}

div[data-baseweb="input"] input {
    background: #ffffff !important;
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
    caret-color: #111827 !important;
}

div[data-baseweb="input"] input::placeholder {
    color: #6b7280 !important;
    -webkit-text-fill-color: #6b7280 !important;
    opacity: 1 !important;
}

/* ==============================
   SELECTBOX
   ============================== */

div[data-baseweb="select"] > div {
    background: #ffffff !important;
    border-radius: 8px !important;
}

div[data-baseweb="select"] span {
    color: #111827 !important;
}

div[data-baseweb="select"] svg {
    fill: #111827 !important;
}

/* Dropdown */

div[role="listbox"] {
    background: #ffffff !important;
}

div[role="option"] {
    background: #ffffff !important;
    color: #111827 !important;
}

div[role="option"] * {
    color: #111827 !important;
}

/* ==============================
   BUTTON
   ============================== */

.stButton > button {
    border-radius: 8px !important;
    font-weight: 700 !important;
}

/* ==============================
   FOOTER
   ============================== */

.footer-text {
    color: #94a3b8 !important;
    text-align: center !important;
    font-size: 13px !important;
}
</style>
""")

# ============================================================
# HEADER
# ============================================================

st.html("""
<div class="app-title">📍 Distance Calculator</div>
<div class="app-subtitle">
    Compare distance and estimated travel time between two locations.
</div>
""")

# ============================================================
# SESSION STATE
# ============================================================

if "source_results" not in st.session_state:
    st.session_state.source_results = []

if "destination_results" not in st.session_state:
    st.session_state.destination_results = []

# ============================================================
# LAYOUT
# ============================================================

left, right = st.columns([1, 2], gap="large")

# ============================================================
# LEFT SIDE
# ============================================================

with left:

    st.html("""
    <div class="section-title">📍 Source</div>
    """)

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

    st.html("""
    <div style="height:25px;"></div>
    <div class="section-title">🏁 Destination</div>
    """)

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

    st.html("""
    <div style="height:25px;"></div>
    """)

    calculate = st.button(
        "🚀 Calculate Route",
        type="primary",
        use_container_width=True
    )

# ============================================================
# RIGHT SIDE
# ============================================================

with right:

    st.html("""
    <div class="route-heading">Route Results</div>
    """)

    # ========================================================
    # CALCULATE
    # ========================================================

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
        # RESULT CARDS
        # ====================================================

        for result in results:

            st.html(f"""
            <div style="
                background:#ffffff;
                border:1px solid #e2e8f0;
                border-radius:14px;
                padding:20px;
                margin-bottom:14px;
                box-shadow:0 2px 8px rgba(0,0,0,0.15);
                color:#111827;
                box-sizing:border-box;
                width:100%;
            ">

                <div style="
                    color:#111827;
                    font-size:20px;
                    font-weight:700;
                    line-height:1.4;
                    margin-bottom:16px;
                ">
                    {result["icon"]} {result["mode"]}
                </div>

                <div style="
                    display:flex;
                    gap:80px;
                    flex-wrap:wrap;
                    color:#111827;
                ">

                    <div>
                        <div style="
                            color:#64748b;
                            font-size:12px;
                            font-weight:700;
                            letter-spacing:0.5px;
                            line-height:1.4;
                        ">
                            DISTANCE
                        </div>

                        <div style="
                            color:#111827;
                            font-size:24px;
                            font-weight:700;
                            line-height:1.4;
                            margin-top:3px;
                        ">
                            {result["distance"]}
                        </div>
                    </div>

                    <div>
                        <div style="
                            color:#64748b;
                            font-size:12px;
                            font-weight:700;
                            letter-spacing:0.5px;
                            line-height:1.4;
                        ">
                            ESTIMATED TIME
                        </div>

                        <div style="
                            color:#111827;
                            font-size:24px;
                            font-weight:700;
                            line-height:1.4;
                            margin-top:3px;
                        ">
                            {result["duration"]}
                        </div>
                    </div>

                </div>

            </div>
            """)

            if result["error"]:
                st.caption(
                    f'{result["mode"]} route unavailable.'
                )

        # ====================================================
        # SELECTED LOCATIONS
        # ====================================================

        st.html("""
        <div class="locations-heading">
            📌 Selected Locations
        </div>
        """)

        st.html(f"""
        <div style="
            background:#ffffff;
            border:1px solid #e2e8f0;
            border-radius:14px;
            padding:20px;
            margin-bottom:14px;
            color:#111827;
            box-sizing:border-box;
            width:100%;
        ">

            <div style="
                color:#111827;
                font-size:15px;
                line-height:1.5;
                margin-bottom:8px;
            ">
                <strong>From:</strong> {source["name"]}
            </div>

            <div style="
                color:#111827;
                font-size:15px;
                line-height:1.5;
            ">
                <strong>To:</strong> {destination["name"]}
            </div>

        </div>
        """)

    # ========================================================
    # INITIAL STATE
    # ========================================================

    else:

        st.html("""
        <div style="
            background:#ffffff;
            border:1px solid #e2e8f0;
            border-radius:14px;
            padding:55px 20px;
            text-align:center;
            color:#111827;
            box-sizing:border-box;
            width:100%;
        ">

            <div style="
                font-size:48px;
                line-height:1.2;
                margin-bottom:10px;
            ">
                🗺️
            </div>

            <div style="
                color:#111827;
                font-size:22px;
                font-weight:700;
                line-height:1.4;
                margin-bottom:8px;
            ">
                Ready to calculate
            </div>

            <div style="
                color:#64748b;
                font-size:15px;
                line-height:1.5;
            ">
                Select your source and destination,
                then click
                <strong style="color:#111827;">
                    Calculate Route
                </strong>.
            </div>

        </div>
        """)

# ============================================================
# FOOTER
# ============================================================

st.divider()

st.html("""
<div class="footer-text">
    Routing powered by OpenStreetMap / OSRM.
</div>
""")
