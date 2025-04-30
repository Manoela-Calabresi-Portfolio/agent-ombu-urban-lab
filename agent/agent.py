import json
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from agent.tools import TOOLS, save_memory, web_search
from agent.prompts import get_system_prompt
import re

load_dotenv()

def agent(messages):
    client = OpenAI()

    # Inject dynamic system prompt before calling the model
    mode = st.session_state.get("mode", "search")
    user_prompt = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    system_prompt = get_system_prompt(user_prompt, mode)
    
    # For refinement mode, add explicit instructions about the selected documents
    if mode == "refine" and hasattr(st.session_state, "selected_for_refinement"):
        selected_docs = list(st.session_state.selected_for_refinement.values())
        if selected_docs:
            refinement_context = "\nSelected documents for refinement:\n"
            for doc in selected_docs:
                refinement_context += f"- {doc['title']}\n"
            system_prompt += refinement_context

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        tools=TOOLS,
        messages=full_messages
    )

    response = completion.choices[0].message

    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            if tool_name == "save_memory":
                return {
                    "message": save_memory(tool_args["memory"]),
                    "results": []
                }

            elif tool_name == "web_search":
                # For refinement mode, ensure the search query includes multiple cities
                if mode == "refine":
                    if "topic" in tool_args:
                        # Get the refinement option and topic from session state
                        refine_option = st.session_state.get("refine_option", "")
                        refined_topic = st.session_state.get("refined_topic_input", "")
                        
                        # Construct a more specific search query based on the refinement option
                        if refine_option == "Focus on a specific aspect":
                            tool_args["topic"] = f"case studies focusing on {refined_topic} in multiple cities"
                        elif refine_option == "Compare specific elements":
                            tool_args["topic"] = f"comparative analysis of {refined_topic} across multiple cities"
                        elif refine_option == "Find connections":
                            tool_args["topic"] = f"connections and relationships of {refined_topic} in urban case studies"
                        elif refine_option == "Extract data/statistics":
                            tool_args["topic"] = f"data and statistics about {refined_topic} in urban case studies"
                        elif refine_option == "Look for data sources":
                            tool_args["topic"] = f"data sources and datasets about {refined_topic} in urban research"
                        elif refine_option == "Look for similar studies":
                            tool_args["topic"] = f"similar urban case studies about {refined_topic}"
                        elif refine_option == "Look for trends":
                            tool_args["topic"] = f"trends and patterns of {refined_topic} in urban case studies"
                        elif refine_option == "Look for case studies":
                            tool_args["topic"] = f"urban case studies about {refined_topic} in multiple cities"
                        else:
                            tool_args["topic"] = f"urban research about {refined_topic} in multiple cities"
                        
                        # Add comparative terms to ensure multi-city results
                        tool_args["topic"] += " comparative analysis multiple cities"
                        
                        # Remove single city focus
                        if "city" in tool_args:
                            del tool_args["city"]
                        
                        # Add default values for required parameters
                        if "timeframe" not in tool_args:
                            tool_args["timeframe"] = "recent years"
                        if "doc_type" not in tool_args:
                            tool_args["doc_type"] = "case studies and research reports"

                # Ensure all required parameters are present
                required_params = ["city", "topic", "timeframe", "doc_type"]
                for param in required_params:
                    if param not in tool_args:
                        tool_args[param] = "multiple cities" if param == "city" else "urban planning"

                search_results = web_search(**tool_args)

                if isinstance(search_results, str):
                    assistant_msg = search_results
                else:
                    if mode == "refine":
                        # Verify results have multiple cities
                        cities = set()
                        for result in search_results:
                            # Extract city names from title and content
                            if "title" in result:
                                cities.update(extract_cities(result["title"]))
                            if "content" in result:
                                cities.update(extract_cities(result["content"]))
                        
                        if len(cities) < 3:
                            # If not enough cities, modify the search to be more specific
                            tool_args["topic"] = f"comparative case studies of {refined_topic} in multiple cities"
                            search_results = web_search(**tool_args)
                        
                        assistant_msg = f"Here's what I found based on your refinement:\n\n"
                        assistant_msg += "\n".join(f"- {r['title']} ({r['url']})" for r in search_results)
                    else:
                        assistant_msg = (
                            f"I found {len(search_results)} documents.\n\n"
                            "📄 Browse them below.\n"
                            "📌 Save your favorites to your Research Box.\n"
                            "🔍 Or ask me to search again with a refined topic."
                        )

                messages.append({
                    "role": "assistant",
                    "content": assistant_msg
                })

                return {
                    "message": assistant_msg,
                    "results": search_results if isinstance(search_results, list) else []
                }

    return {
        "message": response.content if response.content else str(response),
        "results": []
    }

def extract_cities(text):
    """Extract city names from text using common patterns and regex."""
    # Common city name patterns
    city_patterns = [
        r'\b[A-Z][a-z]+(?:[\s-][A-Z][a-z]+)*\s+(?:City|Town|Village)\b',  # City names with City/Town/Village
        r'\b[A-Z][a-z]+(?:[\s-][A-Z][a-z]+)*\b',  # Capitalized words that might be cities
        r'\b(?:New|Old|North|South|East|West)\s+[A-Z][a-z]+\b',  # Cities with directional prefixes
    ]
    
    # Common city names by region
    common_cities = {
        # Asia
        "Tokyo", "Seoul", "Singapore", "Shanghai", "Beijing", "Hong Kong",
        "Bangkok", "Jakarta", "Kuala Lumpur", "Manila", "Taipei", "Osaka",
        "Yokohama", "Busan", "Shenzhen", "Guangzhou", "Mumbai", "Delhi",
        "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune", "Ahmedabad",
        # Europe
        "London", "Paris", "Berlin", "Madrid", "Rome", "Amsterdam",
        "Barcelona", "Munich", "Milan", "Vienna", "Prague", "Warsaw",
        "Budapest", "Athens", "Lisbon", "Dublin", "Copenhagen", "Stockholm",
        # Americas
        "New York", "Los Angeles", "Chicago", "Houston", "Toronto", "Vancouver",
        "Mexico City", "São Paulo", "Rio de Janeiro", "Buenos Aires", "Lima",
        "Bogotá", "Santiago", "Caracas", "Panama City", "San Juan",
        # Africa
        "Cairo", "Lagos", "Nairobi", "Johannesburg", "Cape Town", "Casablanca",
        "Addis Ababa", "Accra", "Dakar", "Tunis", "Algiers", "Khartoum",
        # Oceania
        "Sydney", "Melbourne", "Brisbane", "Perth", "Auckland", "Wellington",
        "Christchurch", "Adelaide", "Hobart", "Darwin"
    }
    
    found_cities = set()
    
    # Check for common city names
    for city in common_cities:
        if city.lower() in text.lower():
            found_cities.add(city)
    
    # Check for city patterns
    for pattern in city_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            city = match.group()
            # Only add if it's not already in the common cities list
            if city not in common_cities:
                found_cities.add(city)
    
    return found_cities
