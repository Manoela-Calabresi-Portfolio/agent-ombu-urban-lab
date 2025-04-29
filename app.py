# 🎯 Import our magical tools
import os
from dotenv import load_dotenv  # This helps us keep secrets safe!
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent.agent import agent
import nest_asyncio
from agent.prompts import get_system_prompt
from agent.tools import web_search
import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster
import math
import requests
import json
from datetime import datetime

# 🔐 Load our secret settings
load_dotenv()

# centralized picture of the logo
st.image("images/logo final_website looka.png", width=600)

# Set page background color
st.markdown("""
<style>
    .stApp {
        background-color: #f0f0f0;
    }
</style>
""", unsafe_allow_html=True)

# explanation of the chatbot in large font and centered
st.write("""
<div style="text-align: center;">
    <h1 style="font-size: 20px; font-style: italic;">an agent to help you research urban trends and build hypotheses for your spatial analysis projects</h1>
</div>
""", unsafe_allow_html=True)    

# Initialize memory
if "stage" not in st.session_state:
    st.session_state.stage = "initial"
if "results" not in st.session_state:
    st.session_state.results = []
if "selected" not in st.session_state:
    st.session_state.selected = []
if "selected_location" not in st.session_state:
    st.session_state.selected_location = None

# Initial input
if st.session_state.stage == "initial":
    # Simple text input for city/region
    city = st.text_input("City / Region / Country")
    
    if city:
        try:
            # Initialize geocoder with a longer timeout
            geolocator = Nominatim(user_agent="urban_lab_app", timeout=10)
            location = geolocator.geocode(city)
            
            if location:
                # Create a folium map centered on the location
                m = folium.Map(location=[location.latitude, location.longitude], zoom_start=12)
                
                # Add a marker for the city center
                folium.Marker(
                    [location.latitude, location.longitude],
                    popup=location.address,
                    tooltip=city
                ).add_to(m)
                
                # Get the OSM ID and type
                osm_id = location.raw.get('osm_id')
                osm_type = location.raw.get('osm_type')
                
                if osm_id and osm_type:
                    try:
                        # Construct the Nominatim API URL for boundary data
                        nominatim_url = f"https://nominatim.openstreetmap.org/details.php?osmtype={osm_type[0].upper()}&osmid={osm_id}&format=json"
                        
                        # Make the request to Nominatim API with timeout and retries
                        session = requests.Session()
                        retry = requests.adapters.HTTPAdapter(max_retries=3)
                        session.mount('https://', retry)
                        
                        response = session.get(
                            nominatim_url, 
                            headers={'User-Agent': 'urban_lab_app'},
                            timeout=10
                        )
                        data = response.json()
                        
                        # Extract the boundary coordinates
                        if 'geometry' in data and 'coordinates' in data['geometry']:
                            # Get the boundary polygon
                            boundary_coords = []
                            # Handle different geometry types
                            if isinstance(data['geometry']['coordinates'], list):
                                # For Polygon type
                                if isinstance(data['geometry']['coordinates'][0], list):
                                    for point in data['geometry']['coordinates'][0]:
                                        if isinstance(point, list) and len(point) >= 2:
                                            # Nominatim returns coordinates in [lon, lat] format, we need [lat, lon]
                                            boundary_coords.append([point[1], point[0]])
                        
                            if boundary_coords:  # Only add polygon if we have valid coordinates
                                # Add the boundary polygon to the map
                                folium.Polygon(
                                    locations=boundary_coords,
                                    color='#3186cc',
                                    fill=True,
                                    fill_color='#3186cc',
                                    fill_opacity=0.2,
                                    popup=f'Boundary of {city}'
                                ).add_to(m)
                    except requests.exceptions.RequestException as e:
                        st.warning("Could not fetch boundary data. Showing location marker only.")
                        st.write(f"Note: {str(e)}")
                
                # Display the map
                folium_static(m)
                
                # Store the location in session state
                st.session_state.selected_location = {
                    "name": city,
                    "lat": location.latitude,
                    "lon": location.longitude
                }
                
                # Show the coordinates
                st.write(f"Selected location: {location.address}")
                st.write(f"Coordinates: {location.latitude}, {location.longitude}")
            else:
                st.warning("Location not found. Please try a different name.")
        except GeocoderTimedOut:
            st.error("Geocoding service timed out. Please try again.")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

    topic = st.text_input("Topic")
    
    # Create year dropdowns for timeframe
    current_year = datetime.now().year
    years = list(range(1900, current_year + 1))
    years.reverse()  # Show most recent years first
    
    col1, col2 = st.columns(2)
    with col1:
        start_year = st.selectbox("From", years, index=0)
    with col2:
        end_year = st.selectbox("To", years, index=0)
    
    # Combine the years into a timeframe string
    timeframe = f"{start_year}-{end_year}"
    
    doc_type = st.selectbox("Document Type", ["All Types", "Reports", "Research Papers", "Urban Strategy Documents", "Technical Reports", "Smart City Projects"])
    num_results = st.number_input("Number of results", min_value=1, max_value=10, value=5)
    
    if st.button("🔍 Start Research"):
        # Store search parameters in session state
        st.session_state.search_params = {
            "topic": topic,
            "timeframe": timeframe,
            "doc_type": doc_type,
            "num_results": num_results
        }
        # (Fake) Tavily search
        st.session_state.results = web_search(st.session_state.selected_location["name"], topic, timeframe, doc_type, num_results)
        st.session_state.stage = "show_results"

# Show results
elif st.session_state.stage == "show_results":
    st.subheader("🔎 Search Results")
    
    # Display the research results
    for idx, result in enumerate(st.session_state.results, 1):
        st.markdown(f"### {idx}. **{result['title']}**\n- **Link**: [{result['url']}]({result['url']})\n- **Key Insights**: {result['content'][:300]}...")
    
    # Add a button to start the chat with custom styling
    st.markdown("""
    <style>
        .big-button {
            display: flex;
            justify-content: center;
            margin: 20px 0;
        }
        .big-button button {
            font-size: 1.5em;
            padding: 15px 30px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .big-button button:hover {
            background-color: #45a049;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="big-button">', unsafe_allow_html=True)
    if st.button("💬 Start Chat About Results", key="chat_button"):
        st.session_state.stage = "chat"
        st.session_state.messages = []  # Initialize chat history
    st.markdown('</div>', unsafe_allow_html=True)

# Chat interface
elif st.session_state.stage == "chat":
    st.subheader("💬 Research Assistant")
    
    # Initialize chat history if not exists
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # Add initial greeting
        st.session_state.messages.append({
            "role": "assistant", 
            "content": f"Hello! I'm your research assistant for {st.session_state.selected_location['name']}. I've analyzed the research about {st.session_state.search_params['topic']} ({st.session_state.search_params['timeframe']}). How can I help you understand these findings better?"
        })
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about the research..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Generate assistant response
        with st.chat_message("assistant"):
            # Create a more natural response based on the user's question
            if any(word in prompt.lower() for word in ["summary", "overview", "main points"]):
                response = f"Here's a summary of the key findings about {st.session_state.search_params['topic']} in {st.session_state.selected_location['name']}:\n\n"
                for idx, result in enumerate(st.session_state.results, 1):
                    response += f"• {result['title']}\n"
                    response += f"  {result['content'][:150]}...\n\n"
                response += "Would you like me to elaborate on any of these points?"
            elif any(word in prompt.lower() for word in ["specific", "details", "more about"]):
                # Find the most relevant result based on the prompt
                relevant_result = next((r for r in st.session_state.results if any(word in r['title'].lower() for word in prompt.lower().split())), None)
                if relevant_result:
                    response = f"Let me provide more details about '{relevant_result['title']}':\n\n"
                    response += f"{relevant_result['content']}\n\n"
                    response += f"You can find the full document here: {relevant_result['url']}"
                else:
                    response = "I couldn't find specific details matching your question. Would you like me to summarize the main findings instead?"
            else:
                response = "I'm here to help you understand the research findings. You can ask me to:\n"
                response += "• Provide a summary of the key findings\n"
                response += "• Explain specific aspects of the research\n"
                response += "• Compare different findings\n"
                response += "• Suggest potential implications\n\n"
                response += "What would you like to know more about?"
            
            st.write(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# Refining stage
elif st.session_state.stage == "refine_search":
    refine_query = st.text_input("Describe how to refine:")

    if st.button("🔍 Refine Search"):
        # Re-run Tavily with refined query
        st.session_state.results += web_search(st.session_state.selected_location["name"], refine_query, timeframe="...")
        st.session_state.stage = "show_results"

# Selecting favorites
elif st.session_state.stage == "select_results":
    selected_numbers = st.text_input("Type the numbers of your favorite results (e.g., 2, 5, 7)")

    if st.button("✅ Confirm Selection"):
        nums = [int(n.strip()) for n in selected_numbers.split(",")]
        st.session_state.selected = [st.session_state.results[i-1] for i in nums]
        st.session_state.stage = "hypothesis"

# Hypothesis creation stage
elif st.session_state.stage == "hypothesis":
    st.subheader("🎯 Let's Create Hypotheses")
    user_idea = st.text_area("Write a thought or idea about the selected articles")

    if st.button("✨ Generate Hypotheses"):
        hypotheses = create_hypothesis([...])  # Use selected articles
        st.markdown(hypotheses)

        if st.button("📥 Export Research Summary"):
            export_to_txt(st.session_state.selected, hypotheses)
