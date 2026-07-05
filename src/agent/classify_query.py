"""
classify_query -- Querying skill's classification step.
Extracts who/what/when the question is about, and which category it falls into.
"""
import json
from src.agent.querying_state import QueryingState
from src.tools.llm_client import get_llm_client, safe_completion
SYSTEM_PROMPT = """You are extracting structured data from a question about team members' work.
Extract the following and respond ONLY with valid JSON, no explanation, no markdown:
{
  "target_person": "<person's name mentioned, or null if none>",
  "target_project": "<project name mentioned, or null if none>",
  "date_str": "<date in YYYY-MM-DD format if a specific date is mentioned, or null>",
  "question_type": one of ["list_people", "collaborators", "status", "activity_on_date", "activity_general", "open_items"]
}
question_type definitions:
- "list_people": asking who works on a PROJECT (e.g. "who worked on the manager agent project")
- "collaborators": asking who a PERSON is working WITH (e.g. "who is Raju pairing with", "who is working with Divyansh")
- "status": asking for current status of a project/task (e.g. "what's the status of X")
- "activity_on_date": asking what someone did on a SPECIFIC date (e.g. "what did X do on 26 june")
- "activity_general": asking what someone has been working on, no specific date (e.g. "what has X been doing")
- "open_items": asking what's pending/outstanding for someone (e.g. "what's pending for X")
Key distinction: "who works on <project>" is list_people. "who is <person> working with" is collaborators.
Rules:
- If a date is mentioned in any form (26 june, June 26, 6/26, yesterday, etc.), convert it to YYYY-MM-DD.
  Assume the current year is 2026 unless stated otherwise.
- Always return valid JSON only
"""
def classify_query_message(state: QueryingState) -> dict:
    """LLM node: extract target_person, target_project, date_str, question_type from a question."""
    client = get_llm_client()
    raw_text = state["raw_text"]
    raw = safe_completion(
        client,
        model="deepseek/deepseek-v4-flash",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        max_tokens=200,
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
        parsed = {
            "target_person": None,
            "target_project": None,
            "date_str": None,
            "question_type": "activity_general",
        }
    return {
        "target_person": parsed.get("target_person"),
        "target_project": parsed.get("target_project"),
        "date_str": parsed.get("date_str"),
        "question_type": parsed.get("question_type", "activity_general"),
    }
