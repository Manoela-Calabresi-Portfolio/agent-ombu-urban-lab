import os
from dotenv import load_dotenv
from datetime import datetime
import streamlit as st
import requests
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from agent.agent import agent

# Load environment variables
load_dotenv()

# Page config and logo
st.image("images/logo final_website looka.png", width=600)
st.markdown("""
<style>
    .stApp {
        background-color: #f0f0f0;
    }
</style>
""", unsafe_allow_html=True)

st.write("""
<div style="text-align: center;">
    <h1 style="font-size: 20px; font-style: italic;">
        an agent to help you research urban trends and build hypotheses for your spatial analysis projects
    </h1>
</div>
""", unsafe_allow_html=True)

# Initialize session state
if "stage" not in st.session_state:
    st.session_state.stage = "initial"
if "results" not in st.session_state:
    st.session_state.results = []
if "selected_location" not in st.session_state:
    st.session_state.selected_location = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "mode" not in st.session_state:
    st.session_state.mode = "search"  # options: search | curate | explore | hypothesis
if "selected_results" not in st.session_state:
    st.session_state.selected_results = []


# Stage: Initial input form
if st.session_state.stage == "initial":
    city = st.text_input("City / Region / Country")

    if city:
        try:
            geolocator = Nominatim(user_agent="urban_lab_app", timeout=10)
            location = geolocator.geocode(city)

            if location:
                m = folium.Map(location=[location.latitude, location.longitude], zoom_start=12)
                folium.Marker([location.latitude, location.longitude], popup=location.address, tooltip=city).add_to(m)

                osm_id = location.raw.get('osm_id')
                osm_type = location.raw.get('osm_type')
                if osm_id and osm_type:
                    try:
                        nominatim_url = f"https://nominatim.openstreetmap.org/details.php?osmtype={osm_type[0].upper()}&osmid={osm_id}&format=json"
                        session = requests.Session()
                        retry = requests.adapters.HTTPAdapter(max_retries=3)
                        session.mount('https://', retry)
                        response = session.get(nominatim_url, headers={'User-Agent': 'urban_lab_app'}, timeout=10)
                        data = response.json()

                        if 'geometry' in data and 'coordinates' in data['geometry']:
                            coords = data['geometry']['coordinates'][0]
                            boundary_coords = [[point[1], point[0]] for point in coords if len(point) >= 2]
                            if boundary_coords:
                                folium.Polygon(locations=boundary_coords, color='#3186cc', fill=True,
                                               fill_color='#3186cc', fill_opacity=0.2,
                                               popup=f'Boundary of {city}').add_to(m)
                    except:
                        st.warning("Could not fetch boundary data.")

                folium_static(m)

                st.session_state.selected_location = {
                    "name": city,
                    "lat": location.latitude,
                    "lon": location.longitude
                }
                st.write(f"Selected location: {location.address}")
                st.write(f"Coordinates: {location.latitude}, {location.longitude}")
            else:
                st.warning("Location not found.")
        except GeocoderTimedOut:
            st.error("Geocoding service timed out.")

    topic = st.text_input("Topic")
    current_year = datetime.now().year
    years = list(range(1900, current_year + 1))[::-1]
    col1, col2 = st.columns(2)
    with col1:
        start_year = st.selectbox("From", years, index=0)
    with col2:
        end_year = st.selectbox("To", years, index=0)
    timeframe = f"{start_year}-{end_year}"
    doc_type = st.selectbox("Document Type", ["All Types", "Reports", "Research Papers", "Urban Strategy Documents", "Technical Reports", "Smart City Projects"])
    num_results = st.number_input("Number of results", min_value=1, max_value=10, value=5)

    if st.button("🔍 Start Research"):
        if not st.session_state.selected_location:
            st.warning("Please enter a valid city and wait for the map to load.")
        else:
            st.session_state.search_params = {
                "city": city,
                "topic": topic,
                "timeframe": timeframe,
                "doc_type": doc_type,
                "num_results": num_results
            }
            initial_prompt = f"Find {str(doc_type).lower()} about {str(topic).lower()} in {city} during {timeframe}."
            st.session_state.messages = [
                {"role": "system", "content": "You are a helpful research assistant for urban planning."},
                {"role": "user", "content": initial_prompt}
            ]
            with st.spinner("🧠 Thinking..."):
                response_obj = agent(st.session_state.messages)
            st.session_state.results = response_obj.get("results", [])
            st.session_state.messages.append({"role": "assistant", "content": response_obj["message"]})
            st.session_state.stage = "chat"
            st.session_state.mode = "curate"
            st.rerun()

# Stage: Chat
elif st.session_state.stage == "chat":
    st.subheader("💬 Research Assistant")

    if st.session_state.mode == "curate":
        st.markdown("### 📄 Search Results")

        for idx, result in enumerate(st.session_state.results, 1):
            with st.expander(f"{idx}. {result['title']}"):
                st.write(result["content"][:300] + "...")
                st.markdown(f"[🔗 View source]({result['url']})")

                if st.button(f"📌 Add to My Box", key=f"add_{idx}"):
                    if result not in st.session_state.selected_results:
                        st.session_state.selected_results.append(result)
                        st.success("✅ Added to your Research Box")
                    else:
                        st.info("Already in your box.")

    # Display chat messages
    for message in st.session_state.messages[1:]:  # Start from index 1 to skip system message
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask me anything about the research..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("🧠 Thinking..."):
            response = agent(st.session_state.messages)

        st.session_state.results = response.get("results", st.session_state.results)
        st.session_state.messages.append({"role": "assistant", "content": response["message"]})
        with st.chat_message("assistant"):
            st.markdown(response["message"])
