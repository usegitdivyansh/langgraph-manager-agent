"""
intent_router -- decides whether an incoming Slack message is a write (an update)
or a query (a question). This is a thin dispatcher, not part of either skill --
Writing and Querying remain fully independent and don't know this exists.
A trailing "?" is treated as a hard, deterministic signal for "query" -- checked
in plain Python before any LLM call, since this is unambiguous in how people
actually type on Slack. Absence of "?" does NOT imply "write" -- many real
questions have no question mark (e.g. "what did X do on Y"), so those still
go through the LLM classifier as before.
"""
import json
from src.tools.llm_client import get_llm_client, safe_completion
ROUTER_PROMPT = """Classify this Slack message as either "write" or "query".
"write" = someone sharing an update about their own work.
  Strong signals: starts with "<Name> here", describes something done/doing/will do,
  no question mark.
  Examples: "Riya here - finished the dashboard today", "will deploy by Sunday",
  "Riya here - starting work on the reporting dashboard"
"query" = someone asking a question about anyone's work or status.
  Strong signals: ends with "?", starts with a question word (what/who/when/where/
  why/how/is/are/does/did), asks about someone ELSE's work or asks for information
  rather than reporting it.
  Examples: "what did Harshit do yesterday", "who is working on the follow-up skill?",
  "what's pending for Divyansh", "is the deploy done?"
Decision rule: if the message ends with "?" or starts with a question word, it is
almost always "query" even if it also contains words like "working" or "status".
If it starts with "<Name> here" or is describing the sender's own actions, it is "write".
Respond ONLY with valid JSON, no explanation:
{{"intent": "write"}} or {{"intent": "query"}}
MESSAGE: {text}"""
def route_intent(text: str) -> str:
    """
    Returns 'write' or 'query'.
    Hard rule: trailing '?' always means query, no LLM call needed.
    Otherwise, asks the LLM. Defaults to 'query' on any parse failure.
    """
    stripped = text.strip()
    if stripped.endswith("?"):
        return "query"
    client = get_llm_client()
    raw = safe_completion(
        client,
        model="deepseek/deepseek-v4-flash",
        messages=[{"role": "user", "content": ROUTER_PROMPT.format(text=text)}],
        max_tokens=50,
        temperature=0,
    )
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        intent = parsed.get("intent", "query")
        if intent in ("write", "query"):
            return intent
    except json.JSONDecodeError:
        pass
    return "query"
