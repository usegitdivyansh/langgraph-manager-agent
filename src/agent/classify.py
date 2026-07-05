"""
Classify node — first LLM call in the graph.
Determines intent (write/query) and extracts structured fields.
Returns a partial AgentState update.
"""

import os
import json
from openai import OpenAI
from src.agent.state import AgentState

SYSTEM_PROMPT = """You are a classifier for a team knowledge management bot.

A Slack message is either:
1. A "write" — an intern sharing an update about their work (e.g. "Riya here — finished the dashboard today")
2. A "query" — someone asking a question about interns' work (e.g. "What is Harshit working on?" or "What has everyone been doing?")

Extract the following and respond ONLY with valid JSON, no explanation, no markdown:

For "write":
{
  "intent": "write",
  "intern_name": "<first name of the intern who sent the update>",
  "update_content": "<the actual update content>",
  "target_interns": null,
  "question": null
}

For "query":
{
  "intent": "query",
  "intern_name": null,
  "update_content": null,
  "target_interns": ["<name>"] or ["all"] if asking about everyone,
  "question": "<the question being asked>"
}

Rules:
- intern_name for write: extract from message context (e.g. "Riya here", "This is Maaz", or just infer from content)
- If the message is unclear or just chatter (greetings, random text), return intent "query" with question being the message text
- Always return valid JSON only
"""


def get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )


def classify_message(state: AgentState) -> dict:
    """
    LLM node: classify the raw Slack message.
    Returns partial state update with intent + extracted fields.
    """
    client = get_llm_client()
    raw_text = state["raw_text"]

    response = client.chat.completions.create(
        model="deepseek/deepseek-v4-flash",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        max_tokens=300,
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if model wraps in ```json
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat as query
        parsed = {
            "intent": "query",
            "intern_name": None,
            "update_content": None,
            "target_interns": ["all"],
            "question": raw_text,
        }

    return {
        "intent": parsed.get("intent", "query"),
        "intern_name": parsed.get("intern_name"),
        "update_content": parsed.get("update_content"),
        "target_interns": parsed.get("target_interns"),
        "question": parsed.get("question"),
    }