import streamlit as st
from services.geocoder import search_places
from services.router import calculate_route
from utils.formatting import format_distance,format_duration

st.set_page_config(
    page_title="Distance Calculator",
    page_icon="📍",
    layout="wide"
)

st.markdown("""
<style>
.block-container{padding-top:2rem;padding-bottom:2rem;max-width:1200px}
.title{font-size:38px;font-weight:700;margin-bottom:4px}
.subtitle{font-size:17px;color:#777;margin-bottom:30px}
.section-title{font-size:20px;font-weight:650;margin-bottom:10px}
.result-card{border:1px solid #e5e7eb;border-radius:14px;padding:20px;margin-bottom:14px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.04)}
.result-title{font-size:20px;font-weight:650;margin-bottom:14px}
.result-label{font-size:13px;color:#777}
.result-value{font-size:24px;font-weight:700;margin-top:3px}
.location-card{border:1px solid #e5e7eb;border-radius:14px;padding:20px;background:#fafafa}
</style>
""",unsafe_allow_html=True)

st.markdown('<div class="title">📍 Distance Calculator</div>',unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Compare distance and estimated travel time between two locations.</div>',
    unsafe_allow_html=True
)

if "source_results" not in st.session_state:
    st.session_state.source_results=[]

if "destination_results" not in st.session_state:
    st.session_state.destination_results=[]

left,right=st.columns([1,2],gap="large")

with left:
    st.markdown('<div class="location-card">',unsafe_allow_html=True)

    st.markdown('<div class="section-title">📍 Source</div>',unsafe_allow_html=True)

    source_query=st.text_input(
        "Search source",
        placeholder="City, airport, landmark or address",
        label_visibility="collapsed",
        key="source_query"
    )

    if source_query and len(source_query.strip())>=3:
        try:
            st.session_state.source_results=search_places(source_query)
        except Exception as e:
            st.error(f"Search failed: {e}")

    source_options=st.session_state.source_results

    source=None

    if source_options:
        source_index=st.selectbox(
            "Select source",
            range(len(source_options)),
            format_func=lambda i:source_options[i]["name"],
            key="source_selection"
        )
        source=source_options[source_index]

    st.markdown("<br>",unsafe_allow_html=True)

    st.markdown('<div class="section-title">🏁 Destination</div>',unsafe_allow_html=True)

    destination_query=st.text_input(
        "Search destination",
        placeholder="City, airport, landmark or address",
        label_visibility="collapsed",
        key="destination_query"
    )

    if destination_query and len(destination_query.strip())>=3:
        try:
            st.session_state.destination_results=search_places(destination_query)
        except Exception as e:
            st.error(f"Search failed: {e}")

    destination_options=st.session_state.destination_results

    destination=None

    if destination_options:
        destination_index=st.selectbox(
            "Select destination",
            range(len(destination_options)),
            format_func=lambda i:destination_options[i]["name"],
            key="destination_selection"
        )
        destination=destination_options[destination_index]

    st.markdown("<br>",unsafe_allow_html=True)

    calculate=st.button(
        "🚀 Calculate Route",
        type="primary",
        use_container_width=True
    )

    st.markdown('</div>',unsafe_allow_html=True)

with right:
    st.markdown("### Route Results")

    if calculate:
        if not source:
            st.warning("Please select a source.")
            st.stop()

        if not destination:
            st.warning("Please select a destination.")
            st.stop()

        if (
            source["latitude"]==destination["latitude"]
            and source["longitude"]==destination["longitude"]
        ):
            st.warning("Source and destination cannot be the same.")
            st.stop()

        modes=[
            ("🚗","Car"),
            ("🚲","Bicycle"),
            ("🚶","Walking")
        ]

        results=[]

        with st.spinner("Calculating routes..."):
            for icon,mode in modes:
                try:
                    result=calculate_route(
                        source["latitude"],
                        source["longitude"],
                        destination["latitude"],
                        destination["longitude"],
                        mode
                    )

                    results.append({
                        "icon":icon,
                        "mode":mode,
                        "distance":format_distance(result["distance_km"]),
                        "duration":format_duration(result["duration_minutes"]),
                        "error":None
                    })

                except Exception as e:
                    results.append({
                        "icon":icon,
                        "mode":mode,
                        "distance":"Unavailable",
                        "duration":"Unavailable",
                        "error":str(e)
                    })

        for result in results:
            st.markdown(
                f"""
                <div class="result-card">
                    <div class="result-title">{result["icon"]} {result["mode"]}</div>
                    <div style="display:flex;gap:80px">
                        <div>
                            <div class="result-label">DISTANCE</div>
                            <div class="result-value">{result["distance"]}</div>
                        </div>
                        <div>
                            <div class="result-label">ESTIMATED TIME</div>
                            <div class="result-value">{result["duration"]}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if result["error"]:
                st.caption(f"{result['mode']} route unavailable.")

        st.markdown("### 📌 Selected Locations")

        st.info(
            f"**From:** {source['name']}\n\n"
            f"**To:** {destination['name']}"
        )

    else:
        st.markdown(
            """
            <div class="result-card" style="text-align:center;padding:60px 20px">
                <div style="font-size:48px">🗺️</div>
                <h3>Ready to calculate</h3>
                <p style="color:#777">
                Select your source and destination, then click
                <b>Calculate Route</b>.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

st.divider()

st.caption("Routing powered by OpenStreetMap / OSRM.")