"""
commit_write -- Writing skill's final node.
Writes the merged draft to the person's wiki file, syncs index.md, detects
follow-up commitments, and adds the person to any explicitly-mentioned project's
roster (deterministic -- collaboration queries depend on it).
"""
import re
from datetime import date
from pathlib import Path
from src.agent.writing_state import WritingState
from src.tools.local_wiki import write_person_file, create_person_file, WIKI_ROOT
from src.tools.llm_client import get_llm_client, safe_completion
from src.tools.project_wiki import detect_mentioned_projects, add_person_to_project
from src.tools.followup_update import get_open_rows_for_person, close_single_open_followup
FOLLOWUP_LIST_PATH = WIKI_ROOT / "follow-up-list.md"
INDEX_PATH = WIKI_ROOT / "index.md"
FOLLOWUP_CHECK_PROMPT = """Analyse this update for TWO independent things.
1. COMMITMENT: does the person say they WILL do something in the future
   (with or without a deadline)?
2. COMPLETION: does the person claim they have FINISHED / COMPLETED / DONE
   a task that was previously assigned to them?
These are independent. A message can be one, the other, both, or neither.
"I finished the report" -> completion, no commitment.
"I will finish the report by Friday" -> commitment, no completion.
"Done with the report, will start the deck tomorrow" -> both.
"Still working on it" -> neither.
UPDATE: {update}
TODAY'S DATE: {today}
Respond ONLY with valid JSON, no explanation, exactly these four keys:
{{"has_commitment": <true|false>, "task": <"short description" or null>, "due_date": <"YYYY-MM-DD, your best estimate, default to 3 days from today if unclear" or null>, "is_completion": <true|false>}}"""
def _ensure_followup_list_exists():
    if not FOLLOWUP_LIST_PATH.exists():
        FOLLOWUP_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        header = "| ID | Person | Task | Assigned | Due | Source | Status |\n|---|---|---|---|---|---|---|\n"
        FOLLOWUP_LIST_PATH.write_text(header, encoding="utf-8")
def _next_followup_id() -> str:
    _ensure_followup_list_exists()
    content = FOLLOWUP_LIST_PATH.read_text(encoding="utf-8")
    existing_ids = re.findall(r"FU-(\d+)", content)
    next_num = max([int(i) for i in existing_ids], default=0) + 1
    return f"FU-{next_num:03d}"
JSON_PARSE_ATTEMPTS = 3
def _ask_followup_llm(update_content: str, today: str) -> dict | None:
    """Call the LLM and parse its JSON. Retries on malformed/truncated JSON --
    the model occasionally cuts a response short mid-object. Returns the parsed
    dict, or None if every attempt failed. Never raises."""
    import json
    client = get_llm_client()
    for attempt in range(1, JSON_PARSE_ATTEMPTS + 1):
        raw = safe_completion(
            client,
            model="deepseek/deepseek-v4-flash",
            messages=[{"role": "user", "content": FOLLOWUP_CHECK_PROMPT.format(update=update_content, today=today)}],
            max_tokens=300,
            temperature=0,
        )
        clean = raw
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()
        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            print(f"[FOLLOWUP LLM] attempt {attempt}/{JSON_PARSE_ATTEMPTS}: malformed JSON: {raw!r}")
            continue
        if not isinstance(parsed, dict):
            print(f"[FOLLOWUP LLM] attempt {attempt}/{JSON_PARSE_ATTEMPTS}: not a JSON object: {parsed!r}")
            continue
        if "has_commitment" not in parsed or "is_completion" not in parsed:
            print(f"[FOLLOWUP LLM] attempt {attempt}/{JSON_PARSE_ATTEMPTS}: missing keys: {parsed!r}")
            continue
        return parsed
    print(f"[FOLLOWUP LLM] all {JSON_PARSE_ATTEMPTS} attempts failed for: {update_content[:80]!r}")
    return None
def _detect_and_log_followup(person_name: str, update_content: str, source_file: str):
    today = str(date.today())
    parsed = _ask_followup_llm(update_content, today)
    if parsed is None:
        return ["(Could not check follow-ups for this message -- the language model "
                "did not respond properly. If you were reporting a completed task, "
                "please say so again.)"]
    notes = []
    # --- COMPLETION (handled first: closing an old row is independent of
    # opening a new one, and a message can do both) ---
    if parsed.get("is_completion"):
        open_rows = get_open_rows_for_person(person_name)
        if len(open_rows) == 1:
            closed_id = close_single_open_followup(person_name)
            if closed_id:
                notes.append(f"Marked {closed_id} as done.")
        elif len(open_rows) > 1:
            listed = ", ".join(r["id"] for r in open_rows)
            notes.append(
                f"{person_name} has {len(open_rows)} open follow-ups ({listed}). "
                f"Which one is complete? Reply with the ID."
            )
        # zero open rows -> nothing to close, stay silent
    # --- COMMITMENT (unchanged behaviour: append a new open row) ---
    if parsed.get("has_commitment"):
        fu_id = _next_followup_id()
        task = parsed.get("task", "unspecified")
        due = parsed.get("due_date", today)
        row = f"| {fu_id} | {person_name} | {task} | {today} | {due} | {source_file} | open |\n"
        with open(FOLLOWUP_LIST_PATH, "a", encoding="utf-8") as f:
            f.write(row)
        notes.append(f"Logged {fu_id} (due {due}).")
    return notes
def _sync_index_people_table(person_name: str, rel_path: str):
    if not INDEX_PATH.exists():
        return
    content = INDEX_PATH.read_text(encoding="utf-8")
    lines = content.splitlines()
    today = str(date.today())
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## People"):
            for j in range(i, min(i + 5, len(lines))):
                if lines[j].strip().startswith("|---"):
                    header_idx = j
                    break
            break
    if header_idx is None:
        return
    for i in range(header_idx + 1, len(lines)):
        line = lines[i]
        if line.strip().startswith("## "):
            break
        if line.startswith("|") and person_name.lower() in line.lower():
            parts = line.split("|")
            if len(parts) >= 4:
                parts[3] = f" {today} "
                lines[i] = "|".join(parts)
            INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
    new_row = f"| {person_name} | {rel_path} | {today} |"
    lines.insert(header_idx + 1, new_row)
    INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
def commit_write(state: WritingState) -> dict:
    person_name = state.get("person_name", "unknown")
    file_path_str = state.get("person_file_path")
    draft = state.get("draft", "")
    is_new = state.get("is_new_person", False)
    if not file_path_str:
        return {"final_response": "Could not commit: no file path resolved."}
    path = Path(file_path_str)
    if is_new and not path.exists():
        create_person_file(person_name, path)
    write_person_file(path, draft)
    rel_path = str(path.relative_to(WIKI_ROOT)).replace("\\", "/")
    _sync_index_people_table(person_name, rel_path)
    update_content = state.get("update_content", "")
    # Deterministic project-roster update: if the update explicitly names a known
    # project, add this person to that project's roster.
    linked_projects = []
    if update_content:
        for project_title in detect_mentioned_projects(update_content):
            add_person_to_project(project_title, person_name)
            linked_projects.append(project_title)
    followup_notes = []
    if update_content:
        followup_notes = _detect_and_log_followup(person_name, update_content, rel_path) or []
    response = f"Wiki updated for {person_name}."
    if linked_projects:
        response += f" (linked to project: {', '.join(linked_projects)})"
    for note in followup_notes:
        response += f"\n{note}"
    return {"final_response": response}
