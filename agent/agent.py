import json
from dotenv import load_dotenv
from openai import OpenAI
from agent.tools import TOOLS, save_memory, web_search, invoke_model

load_dotenv()

def agent(messages):
    client = OpenAI()
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        tools=TOOLS,
        messages=messages
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
                search_results = web_search(**tool_args)

                if isinstance(search_results, str):
                    assistant_msg = search_results
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
        "message": response.content or "The assistant has no response.",
        "results": []
    }
