"""
Reflect node — self-check before committing any output.
Judges the LLM draft against source material.
Returns verdict: pass or fail + reason.
"""

import os
import json
from openai import OpenAI
from src.agent.state import AgentState

REFLECT_WRITE_PROMPT = """You are a quality checker for a wiki update system.

You will be given:
1. The ORIGINAL wiki content
2. The NEW update from the intern
3. The PROPOSED merged wiki

Check that the proposed merged wiki:
- Preserves ALL existing content from the original (nothing deleted or lost)
- Correctly incorporates the new update
- Is well-formatted markdown

Respond ONLY with valid JSON:
{
  "verdict": "pass" or "fail",
  "reason": "brief explanation — required if fail, optional if pass"
}"""

REFLECT_QUERY_PROMPT = """You are a quality checker for a Q&A system.

You will be given:
1. The QUESTION asked
2. The WIKI CONTENT used as source
3. The PROPOSED ANSWER

Check that the proposed answer:
- Directly addresses the question
- Only contains information present in the wiki content (no hallucination)
- Cites which intern's wiki the info came from

Respond ONLY with valid JSON:
{
  "verdict": "pass" or "fail",
  "reason": "brief explanation — required if fail, optional if pass"
}"""


def get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )


def reflect_draft(state: AgentState) -> dict:
    """
    Reflect node: judge the draft before committing.
    Returns partial state update with verdict + reason.
    """
    client = get_llm_client()
    intent = state.get("intent", "query")
    draft = state.get("draft", "")
    retry_count = state.get("retry_count", 0)

    if intent == "write":
        original = list(state.get("doc_contents", {}).values())[0] if state.get("doc_contents") else ""
        update = state.get("update_content", "")
        user_content = f"""ORIGINAL WIKI:
{original}

NEW UPDATE:
{update}

PROPOSED MERGED WIKI:
{draft}"""
        system_prompt = REFLECT_WRITE_PROMPT

    else:
        wiki_content = "\n\n".join(
            f"[{name}]\n{content}"
            for name, content in state.get("doc_contents", {}).items()
        )
        user_content = f"""QUESTION:
{state.get("question", "")}

WIKI CONTENT:
{wiki_content}

PROPOSED ANSWER:
{draft}"""
        system_prompt = REFLECT_QUERY_PROMPT

    response = client.chat.completions.create(
        model="deepseek/deepseek-v4-flash",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=200,
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
        verdict = parsed.get("verdict", "pass")
        reason = parsed.get("reason", "")
    except json.JSONDecodeError:
        verdict = "pass"
        reason = ""

    return {
        "reflection_verdict": verdict,
        "reflection_reason": reason,
        "retry_count": retry_count + 1,
    }