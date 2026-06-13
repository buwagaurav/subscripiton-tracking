from __future__ import annotations

import os
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from subtrack.ai.tools import make_tools


_SYSTEM = (
    "You are SubTrack AI, a concise personal finance assistant for subscription management. "
    "You have tools to query the user's subscriptions, spending totals, and renewal dates.\n\n"
    "Rules:\n"
    "- Always call a tool to fetch real data before answering any spend or renewal question\n"
    "- Format money as $X.XX\n"
    "- Use markdown (bold, bullet lists) — responses are rendered in a chat UI\n"
    "- Be brief and direct; skip preamble\n"
    "- If something isn't found, say so clearly"
)


class _State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _get_llm(tools: list):
    """Return an LLM bound to tools based on LLM_PROVIDER env var.

    Supported values (case-insensitive): anthropic, gemini, groq.
    Defaults to gemini if not set.
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            max_tokens=1024,
        ).bind_tools(tools)

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.environ.get("GROQ_API_KEY"),
            max_tokens=1024,
        ).bind_tools(tools)

    # default: gemini
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        max_output_tokens=1024,
    ).bind_tools(tools)


def _check_api_key() -> str | None:
    """Return an error message if the required API key is missing, else None."""
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    keys = {
        "anthropic": ("ANTHROPIC_API_KEY", "console.anthropic.com"),
        "groq":      ("GROQ_API_KEY",      "console.groq.com"),
        "gemini":    ("GEMINI_API_KEY",     "aistudio.google.com"),
    }
    env_var, url = keys.get(provider, ("GEMINI_API_KEY", "aistudio.google.com"))
    if not os.environ.get(env_var):
        return (
            f"**{env_var} not set.**\n\n"
            f"Add `{env_var}=your_key` to your `.env` file (get one free at {url}), "
            f"then restart the app."
        )
    return None


def _build_graph(user_id: int):
    tools = make_tools(user_id)
    llm = _get_llm(tools)

    def call_model(state: _State) -> dict:
        msgs = [SystemMessage(content=_SYSTEM)] + state["messages"]
        return {"messages": [llm.invoke(msgs)]}

    g = StateGraph(_State)
    g.add_node("agent", call_model)
    g.add_node("tools", ToolNode(tools))
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", tools_condition)
    g.add_edge("tools", "agent")
    return g.compile()


def run_chat(user_id: int, history: list[dict], new_message: str) -> str:
    """Run the agent with conversation history and return the AI text response."""
    err = _check_api_key()
    if err:
        return err

    agent = _build_graph(user_id)

    messages: list[BaseMessage] = []
    for m in history:
        if m["role"] == "user":
            messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            messages.append(AIMessage(content=m["content"]))
    messages.append(HumanMessage(content=new_message))

    result = agent.invoke({"messages": messages})
    last: BaseMessage = result["messages"][-1]

    if isinstance(last.content, str):
        return last.content
    # Content can be a list of blocks when tool-use is mixed in (Anthropic)
    parts = [
        block.get("text", "")
        for block in last.content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(parts) or "I couldn't generate a response — please try again."
