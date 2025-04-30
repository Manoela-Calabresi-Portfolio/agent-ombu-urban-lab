import json
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from agent.tools import TOOLS, save_memory, web_search
from agent.prompts import get_system_prompt

load_dotenv()

def agent(messages):
    client = OpenAI()

    # Inject dynamic system prompt before calling the model
    mode = st.session_state.get("mode", "search")
    user_prompt = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    system_prompt = get_system_prompt(user_prompt, mode)
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
                search_results = web_search(**tool_args)

                if isinstance(search_results, str):
                    assistant_msg = search_results
                else:
                    mode = getattr(st.session_state, "mode", "search")
                    if mode == "refine":
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
