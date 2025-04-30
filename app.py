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
import re

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
if "refined_results" not in st.session_state:
    st.session_state.refined_results = []


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

    # Display search results first
    for idx, result in enumerate(st.session_state.results, 1):
        # Extract year from content
        year_pattern = r'20[0-2]\d|19\d{2}'  # Matches years from 1900-2029
        content_years = re.findall(year_pattern, result.get('content', ''))
        # Use the first year found or empty string if none found
        year = content_years[0] if content_years else ""
        
        # Use URL as fallback if title is just "pdf"
        display_title = result['title'] if result['title'].lower() != "pdf" else result['url'].split('/')[-1]
        if year:
            display_title = f"{display_title} ({year})"

        # Create columns for the result and buttons
        col1, col2, col3 = st.columns([0.8, 0.1, 0.1])
        
        with col1:
            with st.expander(f"{idx}. {display_title}"):
                st.write(result["content"][:300] + "...")
                st.markdown(f"[🔗 View source]({result['url']})")
        
        # Container for success messages
        msg_container = st.container()
        
        with col2:
            if st.button(f"📌", key=f"add_{idx}", help="Add to My Box"):
                if result not in st.session_state.selected_results:
                    st.session_state.selected_results.append(result)
                    with msg_container:
                        st.success("Added to your Research Box", icon="✅")
                else:
                    with msg_container:
                        st.info("Already in your box.", icon="ℹ️")
        
        with col3:
            if st.button(f"🔍", key=f"refine_{idx}", help="Select for refined topic"):
                if result not in st.session_state.refined_results:
                    st.session_state.refined_results.append(result)
                    with msg_container:
                        st.success("Selected for refined topic", icon="✅")
                else:
                    with msg_container:
                        st.info("Already selected for refinement", icon="ℹ️")

    # Show navigation options after results
    st.divider()

    col_box, col_refine = st.columns(2)
    
    with col_box:
        st.markdown("### 📚 Research Box")
        if st.session_state.selected_results:
            col_count, col_clear = st.columns([0.7, 0.3])
            with col_count:
                st.write(f"{len(st.session_state.selected_results)} items selected")
            with col_clear:
                if st.button("🗑️", key="clear_box", help="Clear all selections"):
                    st.session_state.selected_results = []
                    st.rerun()
            
            if st.button("✨ Open Research Box", use_container_width=True, type="primary"):
                st.session_state.stage = "research_box"
                st.rerun()
        else:
            st.info("No items selected yet")
    
    with col_refine:
        st.markdown("### 🔍 For Refinement")
        if st.session_state.refined_results:
            col_count, col_clear = st.columns([0.7, 0.3])
            with col_count:
                st.write(f"{len(st.session_state.refined_results)} items selected")
            with col_clear:
                if st.button("🗑️", key="clear_refine", help="Clear all selections"):
                    st.session_state.refined_results = []
                    st.rerun()
            
            if st.button("🕵🏻‍♀️ Start Refinement", use_container_width=True, type="primary"):
                st.session_state.stage = "refine_search"
                st.rerun()
        else:
            st.info("No items selected yet")

    # Input field
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

# Add new stages
elif st.session_state.stage == "research_box":
    st.subheader("My Research Box")
    if st.button("← Back to Results"):
        st.session_state.stage = "chat"
        st.rerun()
    
    for idx, result in enumerate(st.session_state.selected_results, 1):
        with st.expander(f"{idx}. {result['title']}"):
            st.write(result["content"][:300] + "...")
            st.markdown(f"[🔗 View source]({result['url']})")

elif st.session_state.stage == "refine_search":
    # Navigation options
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        if st.button("← Back to Results"):
            st.session_state.stage = "chat"
            st.rerun()
        if st.button("✨ Go to my research box"):
            st.session_state.stage = "research_box"
            st.rerun()
    
    # Show documents first
    st.markdown("#### Let me help you refine your search 🔍 here are you selected documents:")
    for idx, result in enumerate(st.session_state.refined_results, 1):
        with st.expander(f"{idx}. {result['title']}"):
            st.write(result["content"][:300] + "...")
            st.markdown(f"[🔗 View source]({result['url']})")
    
    # Add a divider between documents and refinement options
    st.divider()
    
    # Then show refinement options
    st.markdown("### What would you like to know about these documents?")
    st.write("Choose an analysis approach and keep refining until you're ready to move to your Research Box.")
    
    # Refinement options in columns for better layout
    col_left, col_right = st.columns(2)
    
    with col_left:
        refine_option = st.radio(
            "Analysis approach:",
            ["Focus on a specific aspect", 
             "Compare specific elements", 
             "Find connections", 
             "Extract data/statistics",
             "Look for data sources"
             "Look for similar studies",
             "Look for trends",
             "Look for case studies",
             "Other"
             ]
        )
    
    with col_right:
        if refine_option == "Focus on a specific aspect":
            refined_topic = st.text_input("What specific aspect would you like to focus on?")
            prompt_prefix = f"Focus on {refined_topic} within these documents"
        elif refine_option == "Compare specific elements":
            refined_topic = st.text_input("What elements would you like to compare?")
            prompt_prefix = f"Compare {refined_topic} across these documents"
        elif refine_option == "Find connections":
            refined_topic = st.text_input("What kind of connections are you looking for?")
            prompt_prefix = f"Identify connections related to {refined_topic} between these documents"
        elif refine_option == "Extract data/statistics":
            refined_topic = st.text_input("What kind of data or statistics are you looking for?")
            prompt_prefix = f"Extract and analyze data about {refined_topic} from these documents"
        elif refine_option == "Look for data sources":
            refined_topic = st.text_input("What type of data sources are you interested in?")
            prompt_prefix = f"Find data sources related to {refined_topic} in these documents"
        elif refine_option == "Look for similar studies":
            refined_topic = st.text_input("What aspects of these studies would you like to compare?")
            prompt_prefix = f"Find similar studies focusing on {refined_topic}"
        elif refine_option == "Look for trends":
            refined_topic = st.text_input("What type of trends are you looking for?")
            prompt_prefix = f"Identify trends related to {refined_topic} in these documents"
        elif refine_option == "Look for case studies":
            refined_topic = st.text_input("What type of case studies are you interested in?")
            prompt_prefix = f"Find case studies related to {refined_topic}"
        else:  # Other
            refined_topic = st.text_input("What would you like to explore?")
            prompt_prefix = f"Explore {refined_topic} in these documents"
        
        if st.button("🔍 Analyze") and refined_topic:
            refined_prompt = f"{prompt_prefix}:\n"
            for result in st.session_state.refined_results:
                refined_prompt += f"\n- {result['title']}"

            st.session_state.messages.append({"role": "user", "content": refined_prompt})

            with st.spinner("🧠 Analyzing..."):
                response = agent(st.session_state.messages)

            # Don't add it again if we're showing it in the expander
            refined_message = response["message"]
            st.session_state.results = response.get("results", st.session_state.results)

            # 🔽 Show the assistant's response in a nice expandable box
            with st.expander("Click to view analysis results"):
                st.markdown(response["message"])

            # ✅ Display the response only if it exists
            if refined_message.strip():
                st.markdown("### Analysis Results")
                st.markdown(refined_message)
            else:
                st.info("No insights were generated from this query.")



