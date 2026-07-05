"""
classify_write -- Writing skill's only LLM classification step.
Assumes every input is an update (no intent detection needed --
Writing skill never receives queries, only Slack updates/minutes/transcripts).
Extracts who the update is about and the update content itself.
"""
import json
from src.agent.writing_state import WritingState
from src.tools.llm_client import get_llm_client, safe_completion
SYSTEM_PROMPT = """You are extracting structured data from a work update.
The message is an intern sharing an update about their work
(e.g. "Riya here — finished the dashboard today").
Extract the following and respond ONLY with valid JSON, no explanation, no markdown:
{
  "person_name": "<first name of the person the update is about>",
  "update_content": "<the actual update content, cleaned up but preserving all details>"
}
Rules:
- person_name: extract from message context (e.g. "Riya here", "This is Maaz", or infer from content)
- If no name is identifiable, set person_name to null
- Always return valid JSON only
"""
def classify_write_message(state: WritingState) -> dict:
    """LLM node: extract person_name + update_content from a raw update message."""
    client = get_llm_client()
    raw_text = state["raw_text"]
    raw = safe_completion(
        client,
        model="deepseek/deepseek-v4-flash",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        max_tokens=300,
        temperature=0,
    )
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"person_name": None, "update_content": raw_text}
    return {
        "person_name": parsed.get("person_name"),
        "update_content": parsed.get("update_content"),
    }
