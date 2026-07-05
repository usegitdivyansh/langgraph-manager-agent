"""
merge_write -- Writing skill's core LLM node.
Frontmatter handled in Python. Output normalized to strip typographic Unicode.
Wikilinks are applied DETERMINISTICALLY in Python after the LLM step -- LLM
link creation was proven unreliable run-to-run, so we never depend on it.
"""
import re
from datetime import date
from src.agent.writing_state import WritingState
from src.tools.llm_client import get_llm_client, safe_completion
from src.tools.local_wiki import apply_wikilinks, known_person_names
_UNICODE_NORMALIZE = {
    "\u2011": "-", "\u2010": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00a0": " ",
}
def _normalize(text: str) -> str:
    for bad, good in _UNICODE_NORMALIZE.items():
        text = text.replace(bad, good)
    return text
MERGE_PROMPT = """You are a wiki manager maintaining a person's knowledge wiki page body.
You do NOT see or write any frontmatter/metadata -- only the Summary and History sections.
You will be given:
1. The CURRENT page body (may be minimal/empty if this is a new person)
2. A NEW UPDATE about their work
Your job: return the COMPLETE updated page body with the new update incorporated.
CRITICAL RULES -- follow exactly:
1. Preserve ALL existing History entries EXACTLY as written, character for character.
2. If a "### {date}" heading ALREADY EXISTS, add the new update as a bullet UNDER it. Do NOT create a second heading for the same date.
3. If no "### {date}" heading exists yet, create exactly ONE new heading, placed at the TOP of the History section.
4. NEVER invent a History entry, name, role, team, or fact not present in the CURRENT body or the NEW UPDATE.
5. Rewrite the ## Summary (3-6 lines) based only on facts in the History. Do not invent a title, team, or role.
6. Write people's names as plain text -- do NOT worry about wikilinks, they are added automatically afterward.
7. Use ONLY plain ASCII hyphens (-) and straight quotes. Never use fancy dashes or curly quotes.
8. Return ONLY the page body starting with "## Summary", no frontmatter, no fences.
CURRENT PAGE BODY:
{current_wiki}
NEW UPDATE:
{update}
TODAY'S DATE: {date}"""
def _split_frontmatter(content: str) -> tuple[str, str]:
    match = re.match(r"^(---\n.*?\n---\n)(.*)", content, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return "", content
def merge_write(state: WritingState) -> dict:
    client = get_llm_client()
    current_full = state.get("current_wiki_content") or ""
    frontmatter, current_body = _split_frontmatter(current_full)
    person_name = state.get("person_name", "Unknown")
    today = str(date.today())
    if not frontmatter:
        frontmatter = f"---\ntitle: {person_name}\ncreated: {today}\nupdated: {today}\ntype: entity\ntags: [intern]\n---\n"
        current_body = "\n## Summary\n(no summary yet)\n\n## History\n"
    else:
        frontmatter = re.sub(r"updated: .*", f"updated: {today}", frontmatter)
    update = state.get("update_content", "")
    reflection_reason = state.get("reflection_reason", "")
    user_content = MERGE_PROMPT.format(
        current_wiki=current_body.strip(),
        update=update,
        date=today,
    )
    if reflection_reason:
        user_content += "\n\nPREVIOUS ATTEMPT FAILED. Reason: " + reflection_reason + "\nPlease fix this."
    body_draft = safe_completion(
        client,
        model="deepseek/deepseek-v4-flash",
        messages=[{"role": "user", "content": user_content}],
        max_tokens=2000,
        temperature=0.1,
    )
    body_draft = _normalize(body_draft.strip())
    # Deterministic wikilink pass -- guarantees known teammates are linked,
    # regardless of whether the LLM did it. This is what Hop 3 depends on.
    body_draft = apply_wikilinks(body_draft, self_name=person_name, known_people=known_person_names())
    full_draft = frontmatter + "\n" + body_draft + "\n"
    return {"draft": full_draft}
