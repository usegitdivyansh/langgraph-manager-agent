"""
reflect_write -- self-check node for Writing skill.
Critically reviews a merge draft. The ONLY failure is content that appears in
neither ORIGINAL nor UPDATE (i.e. genuinely fabricated). New content that came
from the UPDATE is expected and correct -- it must NOT be flagged.
"""
import json
import re
from src.agent.writing_state import WritingState
from src.tools.llm_client import get_llm_client, safe_completion
REFLECT_PROMPT = """You are checking whether a wiki edit invented any information.
The DRAFT is supposed to be ORIGINAL plus the new UPDATE, merged together.
So the DRAFT will naturally contain new content -- that is CORRECT, as long as
that new content came from the UPDATE.
FAIL only if the DRAFT contains a fact, date, name, role, or detail that appears
in NEITHER the ORIGINAL nor the UPDATE (i.e. the model made it up out of nothing).
Content that comes from the UPDATE is always allowed -- never flag it.
Reply with ONLY this JSON, nothing else:
{{"verdict": "pass"}}
or
{{"verdict": "fail", "reason": "<the specific invented detail that is in neither ORIGINAL nor UPDATE>"}}
ORIGINAL:
{original}
UPDATE:
{update}
DRAFT:
{draft}"""
def reflect_write(state: WritingState) -> dict:
    """LLM node: check the merge draft for genuine fabrication (content from neither
    ORIGINAL nor UPDATE). Defaults to FAIL if the checker's response can't be parsed."""
    client = get_llm_client()
    original = state.get("current_wiki_content") or "(empty -- new person)"
    update = state.get("update_content") or ""
    draft = state.get("draft") or ""
    person_name = state.get("person_name") or "unknown"
    retry_count = state.get("retry_count", 0)
    if not draft:
        return {
            "reflection_verdict": "fail",
            "reflection_reason": "No draft was produced.",
            "retry_count": retry_count + 1,
        }
    raw = safe_completion(
        client,
        model="deepseek/deepseek-v4-flash",
        messages=[{"role": "user", "content": REFLECT_PROMPT.format(
            original=original, update=update, draft=draft
        )}],
        max_tokens=150,
        temperature=0,
    )
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        verdict = parsed.get("verdict", "fail")
        reason = parsed.get("reason", "")
    except json.JSONDecodeError:
        verdict = "fail"
        reason = "Reflection checker response could not be parsed."
    # Deterministic Python-level identity check -- unchanged, doesn't rely on the LLM
    title_match = re.search(r"title:\s*(.+)", draft)
    if title_match and person_name.lower() not in title_match.group(1).lower():
        verdict = "fail"
        reason = f"Frontmatter title '{title_match.group(1).strip()}' does not match expected person '{person_name}'."
    if verdict == "fail":
        return {
            "reflection_verdict": "fail",
            "reflection_reason": reason,
            "retry_count": retry_count + 1,
        }
    return {
        "reflection_verdict": "pass",
        "reflection_reason": None,
    }
