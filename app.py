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
from agent.tools import format_result_title
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
    .dialog-bubble {
        background: #fff;
        border-radius: 18px;
        box-shadow: 0 2px 16px rgba(0,0,0,0.07);
        padding: 2rem 2.5rem;
        margin: 2rem auto 1rem auto;
        max-width: 600px;
        font-size: 1.15rem;
        position: relative;
    }
    .dialog-bubble strong {
        font-size: 1.2em;
    }
    .dialog-arrow {
        text-align: center;
        font-size: 2.5rem;
        margin: 0;
        color: #4A90E2;
    }
    .hypothesis-bubble {
        background: #fff;
        border-radius: 18px;
        box-shadow: 0 2px 16px rgba(0,0,0,0.07);
        padding: 2rem 2.5rem 1.2rem 2.5rem;
        margin: 2rem auto 1.5rem auto;
        max-width: 700px;
        text-align: center;
        font-size: 2rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.7em;
    }
    .hypothesis-bubble .emoji {
        font-size: 2.2rem;
    }
</style>
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
    st.session_state.mode = "search"  # options: search | refine | hypothesis
if "selected_results" not in st.session_state:
    st.session_state.selected_results = []
if "refined_results" not in st.session_state:
    st.session_state.refined_results = []
if "refined_search_results" not in st.session_state:
    st.session_state.refined_search_results = []
if "just_analyzed" not in st.session_state:
    st.session_state.just_analyzed = False
if "selected_for_refinement" not in st.session_state:
    st.session_state.selected_for_refinement = {}
if "all_search_results" not in st.session_state:
    st.session_state.all_search_results = []

# Stage: Initial input form
if st.session_state.stage == "initial":
    # Show welcome message only on initial page
    st.markdown("""
    <div class="dialog-bubble">
        <strong>👋 Hello, fellow Urbanist!</strong><br>
        I'm <b>Ombu</b>, an agent to help you research urban trends and build hypotheses for your spatial analysis projects.<br><br>
        <b>What would you like to explore today?</b>
        <ul>
            <li>Evolution of green corridors in Barcelona (2000–2024)</li>
            <li>Case studies on cycling infrastructure in South America</li>
            <li>Post-pandemic strategies for accessibility maps in Seoul</li>
        </ul>
    </div>
    <div class="dialog-arrow">⬇️</div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="dialog-bubble">
        <strong>🌐 What can this tool do?</strong>
        <ul>
            <li>Search serious sources (gov reports, NGOs, academic journals)</li>
            <li>Summarize them in 3 bullets</li>
            <li>Help you build hypotheses for spatial analysis</li>
            <li>Let you save and compare documents in your Research Box</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Start by defining your research parameters:")

    city = st.text_input("City / Region / Country")

    if city:
        try:
            geolocator = Nominatim(user_agent="urban_lab_app", timeout=10)
            location = geolocator.geocode(city)

            if location:
                m = folium.Map(
                    location=[location.latitude, location.longitude],
                    zoom_start=12,
                    tiles='CartoDB positron',  # Light grayscale map
                    attr='CartoDB'
                )

                osm_id = location.raw.get('osm_id')
                osm_type = location.raw.get('osm_type')
                if osm_id and osm_type:
                    try:
                        # Get the boundary data from Nominatim
                        nominatim_url = f"https://nominatim.openstreetmap.org/details.php?osmtype={osm_type[0].upper()}&osmid={osm_id}&class=boundary&format=json"
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (compatible; urban_lab_app/1.0)',
                            'Accept': 'application/json'
                        }
                        response = requests.get(nominatim_url, headers=headers, timeout=15)
                        
                        if response.ok:
                            data = response.json()
                            if 'geometry' in data and 'coordinates' in data['geometry']:
                                coords = data['geometry']['coordinates']
                                boundary_coords = []
                                
                                try:
                                    # Debug the actual values
                                    st.write("Raw coordinates:", coords)
                                    
                                    # Create a circle with 10km radius around the city center
                                    folium.Circle(
                                        location=[location.latitude, location.longitude],
                                        radius=10000,  # 10km in meters
                                        color='#4A90E2',      # Blue border
                                        weight=2,             # Border width
                                        fill=True,
                                        fill_color='#4A90E2', # Blue fill
                                        fill_opacity=0.3,     # Semi-transparent
                                        popup=f'10km radius around {city}'
                                    ).add_to(m)
                                    
                                except Exception as e:
                                    st.warning(f"Error processing coordinates: {str(e)}")
                                    st.write("Raw coordinates:", coords)
                            else:
                                st.warning("No boundary data found for this location")
                                st.write("Available data keys:", list(data.keys()))
                                if 'geometry' in data:
                                    st.write("Geometry keys:", list(data['geometry'].keys()))
                        else:
                            st.warning(f"Failed to fetch boundary data: HTTP {response.status_code}")
                            st.write("Response:", response.text[:500])
                    except Exception as e:
                        st.warning(f"Error fetching boundary data: {str(e)}")

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
    st.markdown("**Document Type**")
    doc_types = ["Reports", "Research Papers", "Urban Strategy Documents", "Technical Reports", "Smart City Projects"]

    # Use multiselect to allow checking more than one document type
    # By default, no document types are selected; user must choose
    selected_doc_types = st.multiselect(
        "Select one or more document types:",
        options=doc_types,
        default=[]
    )

    # Define doc_type for downstream use
    if not selected_doc_types:
        doc_type = "All Types"
    elif len(selected_doc_types) == 1:
        doc_type = selected_doc_types[0]
    else:
        doc_type = ", ".join(selected_doc_types)

    if not selected_doc_types:
        selected_doc_types.append("All Types")

    doc_types_str = ", ".join(selected_doc_types)
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
            st.session_state.all_search_results = response_obj.get("results", []).copy()  # Store original results
            st.session_state.messages.append({"role": "assistant", "content": response_obj["message"]})
            st.session_state.stage = "chat"
            st.session_state.mode = "refine"
            st.rerun()

# Stage: Chat
elif st.session_state.stage == "chat":
    # add a back to research parameters button
    if st.button("← Back to Research Parameters"):
        st.session_state.stage = "initial"
        st.rerun()

    st.subheader("💬 Research Assistant")

    # Display search results first
    for idx, result in enumerate(st.session_state.results, 1):
        display_title = format_result_title(result)
        
        # Create columns for the result and buttons
        col1, col2, col3 = st.columns([0.8, 0.1, 0.1])
        
        with col1:
            with st.expander(f"{idx}. {display_title}"):
                st.write(result["content"][:300] + "...")
                st.markdown(f"[🔗 View source]({result['url']})")
        
        # Container for success messages
        msg_container = st.container()
        
        with col2:
            is_in_box = result in st.session_state.selected_results
            if st.button("📌", key=f"add_refined_{idx}", help="Add to My Box"):
                if not is_in_box:
                    st.session_state.selected_results.append(result)
                st.rerun()
        
        with col3:
            is_in_refinement = result in st.session_state.refined_results
            if st.button("🔍", key=f"refine_refined_{idx}", help="Select for refined topic"):
                if not is_in_refinement:
                    st.session_state.refined_results.append(result)
                st.rerun()

    # Show navigation options after results
    st.divider()

    col_box, col_refine = st.columns(2)
    
    
    with col_box:
        st.markdown("###### Sending to Research Box: ")
        if st.session_state.selected_results:
            col_count, col_clear = st.columns([0.7, 0.3])
            with col_count:
                st.write(f"{len(st.session_state.selected_results)} items selected")
            with col_clear:
                if st.button("🗑️", key="clear_box", help="Clear all selections"):
                    st.session_state.selected_results = []
                    st.rerun()
            
            if st.button(f"✨ Go to my Research Box", use_container_width=True, type="primary"):
                st.session_state.stage = "research_box"
                st.rerun()
        else:
            st.info("No items selected yet")
    
    with col_refine:
        st.markdown("###### Sending to the Refinement Lab: ")
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
                st.session_state.mode = "refine"
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
    
    # Show count of items selected for refinement
    if st.session_state.refined_results:
        st.write(f"🔎{len(st.session_state.refined_results)} items selected for refinement")
    
    for idx, result in enumerate(st.session_state.selected_results, 1):
        display_title = format_result_title(result)
        
        # Create columns for the result and buttons
        col1, col2, col3, col4 = st.columns([0.75, 0.125, 0.125, 0.125])
        
        with col1:
            with st.expander(f"{idx}. {display_title}"):
                st.write(result["content"][:300] + "...")
                st.markdown(f"[🔗 View source]({result['url']})")
        
        with col2:
            is_in_refinement = any(r["url"] == result["url"] for r in st.session_state.refined_results)
            button_icon = "✅" if is_in_refinement else "🔎"
            if st.button(button_icon, key=f"refine_box_{idx}", help="Send to Refinement Lab"):
                if not is_in_refinement:
                    st.session_state.refined_results.append(result)
                    st.success(f"Added to refinement: {display_title}")
                else:
                    st.session_state.refined_results = [r for r in st.session_state.refined_results if r["url"] != result["url"]]
                    st.info(f"Removed from refinement: {display_title}")
                st.rerun()
        
        with col3:
            is_in_hypothesis = any(r["url"] == result["url"] for r in st.session_state.get("hypothesis_results", []))
            button_icon = "✅" if is_in_hypothesis else "🔮"
            if st.button(button_icon, key=f"hypothesis_box_{idx}", help="Take this to the Hypothesis Lab"):
                if not is_in_hypothesis:
                    if "hypothesis_results" not in st.session_state:
                        st.session_state.hypothesis_results = []
                    st.session_state.hypothesis_results.append(result)
                    st.success(f"Added to Hypothesis Lab: {display_title}")
                else:
                    st.session_state.hypothesis_results = [r for r in st.session_state.hypothesis_results if r["url"] != result["url"]]
                    st.info(f"Removed from Hypothesis Lab: {display_title}")
                st.rerun()
        
        with col4:
            if st.button("🗑️", key=f"delete_box_{idx}", help="Delete this result"):
                # Remove from both selected and refined results
                st.session_state.selected_results = [r for r in st.session_state.selected_results if r["url"] != result["url"]]
                st.session_state.refined_results = [r for r in st.session_state.refined_results if r["url"] != result["url"]]
                if "hypothesis_results" in st.session_state:
                    st.session_state.hypothesis_results = [r for r in st.session_state.hypothesis_results if r["url"] != result["url"]]
                st.rerun()

    # Add Clear Box button at the bottom
    st.divider()
    col_clear, col_hypothesis = st.columns([0.5, 0.5])
    with col_clear:
        if st.button("🗑️ Clear Box", use_container_width=True):
            st.session_state.selected_results = []
            st.session_state.refined_results = []
            if "hypothesis_results" in st.session_state:
                st.session_state.hypothesis_results = []
            st.rerun()
    
    with col_hypothesis:
        hypothesis_count = len(st.session_state.get("hypothesis_results", []))
        if st.button(f"🔮 Take me now to the Hypothesis Lab \n\n ({hypothesis_count} studies)", use_container_width=True, type="primary"):
            st.session_state.stage = "hypothesis"
            st.rerun()

elif st.session_state.stage == "refine_search":
    # Navigation options
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        if st.button("← Back to Results"):
            st.session_state.stage = "chat"
            st.rerun()
    
    if st.button(f"✨ Go to my research box\n({len(st.session_state.selected_results)} studies)", use_container_width=True):
        st.session_state.stage = "research_box"
        st.rerun()
    
    # Show documents first
    st.markdown("#### Let me help you refine your search. Start by selecting the documents you want to refine:")
    
    # Ensure selected_for_refinement is a dictionary
    if not isinstance(st.session_state.selected_for_refinement, dict):
        st.session_state.selected_for_refinement = {}
    
    # Show count of selected documents
    if st.session_state.selected_for_refinement:
        st.markdown(f"**Selected {len(st.session_state.selected_for_refinement)} documents for refinement:**")
        # Display selected documents first
        for idx, (url, result) in enumerate(st.session_state.selected_for_refinement.items(), 1):
            display_title = format_result_title(result)
            st.markdown(f"{idx}. **{display_title}** ✅")
        st.divider()
    
    # Then show all documents
    for idx, result in enumerate(st.session_state.refined_results, 1):
        display_title = format_result_title(result)
        is_selected = result["url"] in st.session_state.selected_for_refinement
        
        # Create columns for the result and buttons
        col1, col2, col3, col4 = st.columns([0.7, 0.1, 0.1, 0.1])
        
        with col1:
            with st.expander(f"{idx}. {display_title}" + (" ✅" if is_selected else "")):
                st.write(result["content"][:300] + "...")
                st.markdown(f"[🔗 View source]({result['url']})")
        
        with col2:
            is_in_box = any(r["url"] == result["url"] for r in st.session_state.selected_results)
            if st.button("📌", key=f"add_selected_{idx}", help="I want to send this to my research box"):
                if not is_in_box:
                    st.session_state.selected_results.append(result)
                else:
                    st.session_state.selected_results = [r for r in st.session_state.selected_results if r["url"] != result["url"]]
                st.rerun()
        
        with col3:
            button_icon = "✅" if is_selected else "⏹️"
            if st.button(button_icon, key=f"refine_selected_{idx}", help="Select this document for refinement"):
                if not is_selected:
                    st.session_state.selected_for_refinement[result["url"]] = result
                    st.success(f"Selected for refinement: {display_title}")
                else:
                    del st.session_state.selected_for_refinement[result["url"]]
                    st.info(f"Deselected from refinement: {display_title}")
                st.rerun()

        with col4:
            if st.button("🗑️", key=f"delete_selected_{idx}", help="Remove this document from the list"):
                # Remove from refined results
                st.session_state.refined_results = [r for r in st.session_state.refined_results if r["url"] != result["url"]]
                
                # Clean up from other lists if needed
                st.session_state.selected_results = [r for r in st.session_state.selected_results if r["url"] != result["url"]]
                if result["url"] in st.session_state.selected_for_refinement:
                    del st.session_state.selected_for_refinement[result["url"]]
                
                st.rerun()

    # Add a divider between documents and refinement options
    st.divider()
    
    # Show count of selected documents for refinement
    if st.session_state.selected_for_refinement:
        st.write(f"Selected {len(st.session_state.selected_for_refinement)} documents for refinement")
    
    # Add Clear Refinement Lab button
    if st.button("🗑️ Clear Refinement Lab", key="clear_refinement_lab_btn_1", use_container_width=True):
        st.session_state.refined_results = []
        st.session_state.refined_search_results = []
        st.session_state.selected_for_refinement = {}
        st.rerun()
    
    # Then show refinement options
    st.markdown("""
        <style>
        /* Style for text input */
        div[data-baseweb="input"] {
            background-color: #cb8377 !important;
        }
        div[data-baseweb="input"] input {
            background-color: #cb8377 !important;
            color: white !important;
            border-color: white !important;
        }
        div[data-baseweb="input"] input::placeholder {
            color: rgba(255, 255, 255, 0.7) !important;
        }
        </style>
        <div>
            <h3 style="margin: 0;">How would you like to further explore these documents?</h3>
            <p style="margin-top: 10px;">Choose an analysis approach and keep refining until you're ready to move to your Research Box.</p>
        </div>
    """, unsafe_allow_html=True)

    with st.container():
        col_left, col_right = st.columns(2)
        
        with col_left:
            refine_option = st.radio(
                "Analysis approach:",
                [
                    "Focus on a specific aspect",
                    "Compare specific elements", 
                    "Find connections", 
                    "Extract data/statistics",
                    "Look for data sources",
                    "Look for similar studies",
                    "Look for trends",
                    "Look for case studies",
                    "Other"
                ],
                key="refine_option"
            )
        
        with col_right:
            if refine_option == "Focus on a specific aspect":
                refined_topic = st.text_input("What specific aspect would you like to focus on?", key="refined_topic_input")
                prompt_prefix = f"Focus on {refined_topic} within these documents"
            elif refine_option == "Compare specific elements":
                refined_topic = st.text_input("What elements would you like to compare?", key="refined_topic_input")
                prompt_prefix = f"Compare {refined_topic} across these documents"
            elif refine_option == "Find connections":
                refined_topic = st.text_input("What kind of connections are you looking for?", key="refined_topic_input")
                prompt_prefix = f"Identify connections related to {refined_topic} between these documents"
            elif refine_option == "Extract data/statistics":
                refined_topic = st.text_input("What kind of data or statistics are you looking for?", key="refined_topic_input")
                prompt_prefix = f"Extract and analyze data about {refined_topic} from these documents"
            elif refine_option == "Look for data sources":
                refined_topic = st.text_input("What type of data sources are you interested in?", key="refined_topic_input")
                prompt_prefix = f"Find data sources related to {refined_topic} in these documents"
            elif refine_option == "Look for similar studies":
                refined_topic = st.text_input("What aspects of these studies would you like to compare?", key="refined_topic_input")
                prompt_prefix = f"Find similar studies focusing on {refined_topic}"
            elif refine_option == "Look for trends":
                refined_topic = st.text_input("What type of trends are you looking for?", key="refined_topic_input")
                prompt_prefix = f"Identify trends related to {refined_topic} in these documents"
            elif refine_option == "Look for case studies":
                refined_topic = st.text_input("What type of case studies are you interested in?", key="refined_topic_input")
                prompt_prefix = f"Find case studies related to {refined_topic}"
            else:  # Other
                refined_topic = st.text_input("What would you like to explore?", key="refined_topic_input")
                prompt_prefix = f"Explore {refined_topic} in these documents"

            analyze_button = st.button("🔍 Analyze", key="analyze_btn")

        if analyze_button and refined_topic:
            st.session_state.just_analyzed = True
            st.session_state.mode = "refine"

            # Construct the refined prompt
            refined_prompt = f"{prompt_prefix}:\n"
            refined_prompt += "\nSelected documents for reference:\n"
            for result in st.session_state.refined_results:
                refined_prompt += f"\n- {result['title']}"
            
            # The system prompt from prompts.py will be automatically used by the agent
            # when mode="refine" is set in session state
            st.session_state.messages = [
                {"role": "user", "content": refined_prompt}
            ]

            with st.spinner("🧠 Analyzing..."):
                response = agent(st.session_state.messages)
                if response.get("results"):
                    # Store all results in both places
                    st.session_state.refined_search_results = response["results"].copy()
                    st.session_state.all_search_results = response["results"].copy()
                st.session_state.messages.append({"role": "assistant", "content": response["message"]})

        # Show refined results outside the analyze button block
        if st.session_state.refined_search_results:
            st.markdown("### 🔍 Refined Search Results")
            for idx, result in enumerate(st.session_state.refined_search_results, 1):
                display_title = format_result_title(result)
                
                # Create columns for the result and buttons
                col1, col2, col3, col4 = st.columns([0.7, 0.1, 0.1, 0.1])
                
                with col1:
                    with st.expander(f"{idx}. {display_title}"):
                        st.write(result["content"][:300] + "...")
                        st.markdown(f"[🔗 View source]({result['url']})")
                
                with col2:
                    is_in_box = any(r["url"] == result["url"] for r in st.session_state.selected_results)
                    if st.button("📌", key=f"add_refined_{idx}", help="I want to send this to my research box"):
                        if not is_in_box:
                            st.session_state.selected_results.append(result)
                            st.success(f"Added to Research Box: {display_title}")
                        else:
                            st.session_state.selected_results = [r for r in st.session_state.selected_results if r["url"] != result["url"]]
                            st.info(f"Removed from Research Box: {display_title}")
                        st.rerun()
                
                with col3:
                    is_selected = result["url"] in st.session_state.selected_for_refinement
                    button_icon = "✅" if is_selected else "⏹️"
                    if st.button(button_icon, key=f"refine_refined_{idx}", help="Select this document for refinement"):
                        if not is_selected:
                            st.session_state.selected_for_refinement[result["url"]] = result
                            st.success(f"Selected for refinement: {display_title}")
                        else:
                            del st.session_state.selected_for_refinement[result["url"]]
                            st.info(f"Deselected from refinement: {display_title}")
                        st.rerun()

                with col4:
                    if st.button("🗑️", key=f"delete_refined_{idx}", help="Remove this document and show a new one"):
                        # Get a new result that's not currently in refined_search_results
                        current_urls = {r["url"] for r in st.session_state.refined_search_results}
                        available_results = [r for r in st.session_state.all_search_results if r["url"] not in current_urls]
                        
                        if available_results:
                            # Get the first available new result
                            new_result = available_results[0]
                            
                            # Replace the current result with the new one
                            st.session_state.refined_search_results[idx - 1] = new_result
                            
                            # Clean up from other lists if needed
                            st.session_state.selected_results = [r for r in st.session_state.selected_results if r["url"] != result["url"]]
                            if result["url"] in st.session_state.selected_for_refinement:
                                del st.session_state.selected_for_refinement[result["url"]]
                            
                            st.success(f"Replaced with: {format_result_title(new_result)}")
                        else:
                            # If no new results available, remove the current one
                            st.session_state.refined_search_results = [r for r in st.session_state.refined_search_results if r["url"] != result["url"]]
                            st.warning("No more new results available")
                        
                        st.rerun()

            # Show counts after the results
            if st.session_state.selected_for_refinement:
                st.write(f"Selected {len(st.session_state.selected_for_refinement)} documents for refinement")
            if st.session_state.selected_results:
                st.write(f"Added {len(st.session_state.selected_results)} documents to Research Box")

            # Add Clear Refinement Lab button at the bottom
            st.divider()
            if st.button("🗑️ Clear Refinement Lab", key="clear_refinement_lab_btn_2", use_container_width=True):
                st.session_state.refined_results = []
                st.session_state.refined_search_results = []
                st.session_state.selected_for_refinement = {}
                st.rerun()

elif st.session_state.stage == "hypothesis":
    st.markdown("""
    <div class="hypothesis-bubble">
        <span class="emoji">🔮</span> Hypothesis Lab
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Back to Research Box"):
        st.session_state.stage = "research_box"
        st.rerun()

    if "hypothesis_results" in st.session_state and st.session_state.hypothesis_results:
        st.write(f"Based on {len(st.session_state.hypothesis_results)} selected documents:")

        for idx, result in enumerate(st.session_state.hypothesis_results, 1):
            display_title = format_result_title(result)
            with st.expander(f"{idx}. {display_title}"):
                st.write(result["content"][:300] + "...")
                st.markdown(f"[🔗 View source]({result['url']})")

        st.markdown("---")

        if "initial_hypotheses" not in st.session_state:
            if st.button("✨ Generate Hypotheses"):
                prompt = (
                    "You are an urban research assistant helping generate spatial analysis hypotheses.\n"
                    "Based on the following studies, suggest exactly 3 researchable hypotheses that could be explored using spatial data.\n"
                    "Each hypothesis should:\n"
                    "- Be clearly worded (1–2 sentences)\n"
                    "- Mention a spatial trend, relationship, or variable (e.g., green space access, density, mobility, land use)\n"
                    "- Be relevant to urban planning or geography\n"
                    "Format them as a numbered list (1., 2., 3.).\n"
                    "If you cannot find enough hypotheses, make them up based on the document titles. "
                    "Return only a numbered list of 3 hypotheses, nothing else. Do not include any introduction or summary.\n\n"
                )
                for result in st.session_state.hypothesis_results:
                    prompt += f"- {result['title']}\n"

                st.session_state.messages = [{"role": "user", "content": prompt}]
                st.session_state.mode = "hypothesis"
                st.session_state.trigger_hypothesis_generation = True
                st.rerun()

        if st.session_state.get("trigger_hypothesis_generation"):
            with st.spinner("🧠 Thinking..."):
                response = agent(st.session_state.messages)
                st.session_state.initial_hypotheses = response["message"]
            st.session_state.trigger_hypothesis_generation = False
            st.rerun()

        if "initial_hypotheses" in st.session_state:
            st.markdown("### ✅ Suggested Hypotheses")

            # Extract numbered hypotheses (1., 2., 3.)
            hypotheses = re.findall(r"\d+\.\s+(.*?)(?=\n\d+\.|\Z)", st.session_state.initial_hypotheses, re.DOTALL)
            # Fallback: try bullet points
            if len(hypotheses) < 3:
                hypotheses += re.findall(r"^-\s+(.*?)(?=\n-|\\Z)", st.session_state.initial_hypotheses, re.MULTILINE | re.DOTALL)

            if len(hypotheses) >= 3:
                hypotheses = hypotheses[:3]
                selected = st.radio("Select one hypothesis to refine:", hypotheses, key="selected_hypothesis")
                if selected:
                    st.markdown("---")
                    st.markdown("### 🗣️ Chat to refine this hypothesis")
                    st.info("Great choice! Let's refine this hypothesis together. What would you like to adjust or explore further?")

                    if "chat_history" not in st.session_state:
                        st.session_state.chat_history = [{"role": "system", "content": f"You are helping refine this hypothesis: '{selected}'"}]

                    if prompt := st.chat_input("Refine your hypothesis..."):
                        st.session_state.chat_history.append({"role": "user", "content": prompt})
                        with st.chat_message("user"):
                            st.markdown(prompt)

                        with st.spinner("Thinking..."):
                            response = agent(st.session_state.chat_history)
                            st.session_state.chat_history.append({"role": "assistant", "content": response["message"]})

                    for msg in st.session_state.chat_history:
                        with st.chat_message(msg["role"]):
                            st.markdown(msg["content"])
            else:
                st.warning("Could not extract 3 hypotheses. Try generating again or check the raw LLM response below.")
                st.markdown("#### Raw LLM response:")
                st.code(st.session_state.initial_hypotheses)
                if st.button("🔄 Retry Hypothesis Generation"):
                    del st.session_state["initial_hypotheses"]
                    st.session_state.trigger_hypothesis_generation = True
                    st.rerun()

    else:
        st.info("Select documents to use in the Hypothesis Lab.")


