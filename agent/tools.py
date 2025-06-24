import os
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()
import uuid
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI
from tavily import TavilyClient
from datetime import datetime, timezone
import requests
import json
import re

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Initialize Pinecone for vector database
pc = Pinecone(os.getenv("PINECONE_API_KEY"))
# Initialize the vector database index
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))
# Initialize OpenAI for embeddings 
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define the tools
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save a memory to the vector database",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory": {"type": "string"}
                },
                "required": ["memory"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for urban planning information, reports, studies, or academic papers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "topic": {"type": "string"},
                    "timeframe": {"type": "string"},
                    "doc_type": {"type": "string"},
                    "num_results": {"type": "integer", "default": 5}
                },
                "required": ["city", "topic", "timeframe", "doc_type"]
            },
        },
    }
]


# Function to get the embeddings of a string
def get_embeddings(string_to_embed):
    response = client.embeddings.create(
        input=string_to_embed,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def save_memory(memory):
    # Step 1: Embed the memory
    vector = get_embeddings(memory)
    # Step 2: Build the vector document to be stored
    user_id = "1234"
    path = "user/{user_id}/recall/{event_id}"
    current_time = datetime.now(tz=timezone.utc)
    path = path.format(
        user_id=user_id,
        event_id=str(uuid.uuid4()),
    )
    documents = [
        {
            "id": str(uuid.uuid4()),
            "values": vector,
            "metadata": {
                "payload": memory,
                "path": path,
                "timestamp": str(current_time),
                "type": "recall", # Define the type of document i.e recall memory
                "user_id": user_id,
            },
        }
    ]
    # Step 3: Store the vector document in the vector database
    index.upsert(
        vectors=documents,
        namespace=os.getenv("PINECONE_NAMESPACE")
    )
    return "Memory saved successfully"

def load_memories(prompt):
    user_id = "1234"
    top_k = 3
    vector = get_embeddings(prompt)
    response = index.query(
        vector=vector,
        filter={
            "user_id": {"$eq": user_id},
            "type": {"$eq": "recall"},
        },
        namespace=os.getenv("PINECONE_NAMESPACE"),
        include_metadata=True,
        top_k=top_k,
    )
    memories = []
    if matches := response.get("matches"):
        memories = [m["metadata"]["payload"] for m in matches]
        memories
    return memories

def web_search(city, topic, timeframe, doc_type, num_results=5):
    # Construct a smarter query including the selected document type
    query = f"{doc_type} about {topic} in {city} during {timeframe}"

    url = "https://api.tavily.com/search"
    headers = {"Authorization": f"Bearer {TAVILY_API_KEY}"}
    payload = {"query": query, "num_results": num_results}

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("results", [])
    else:
        print("Error:", response.text)
        return []

    
def invoke_model(messages):
    # Initialize the OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Make a ChatGPT API call with tool calling
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )

    return completion.choices[0].message.content

def format_result_title(result):
    # Extract year from content - look for publication year patterns
    year_pattern = r'(?:published|released|publication date|date of publication|year)[:\s]+(?:19|20)\d{2}|(?:19|20)\d{2}'
    content_years = re.findall(year_pattern, result.get('content', ''), re.IGNORECASE)
    # Use the first year found or empty string if none found
    year = content_years[0] if content_years else ""
    
    # Extract city name - look in the full content
    # Common city names pattern
    city_pattern = r'\b(?:Paris|Bogota|Curitiba|Mexico City|Tokyo|Sydney|Canberra|Orlando|Seattle|New York|Santiago|Lima|London|Berlin|Madrid|Rome|Amsterdam|Barcelona|Vienna|Copenhagen|Stockholm|Munich|Hamburg|Milan|Brussels|Prague|Warsaw|Budapest|Dublin|Lisbon|Helsinki|Oslo|Athens|Rotterdam|Valencia|Frankfurt|Seville|Glasgow|Manchester|Birmingham|Lyon|Turin|Naples|Marseille|Leeds|Krakow|Porto|Riga|Vilnius|Tallinn|Sofia|Bucharest|Zagreb|Ljubljana|Bratislava)\b'
    
    # Look for cities in the full content
    cities = re.findall(city_pattern, result.get('content', ''), re.IGNORECASE)
    # Get the first city found
    city = cities[0].title() if cities else ""
    
    # Get the base title
    base_title = result['title'] if result['title'].lower() != "pdf" else result['url'].split('/')[-1]
    
    # Format the title
    if city and year:
        return f"{city} ({year}): {base_title}"
    elif city:
        return f"{city}: {base_title}"
    elif year:
        return f"({year}): {base_title}"
    else:
        return base_title

# create a function to help the user to create a hypothesis for a spatial analysis by prompting the user with questions and display the hypothesis in a bullet point format 
def create_hypothesis(messages):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    return completion.choices[0].message.content

