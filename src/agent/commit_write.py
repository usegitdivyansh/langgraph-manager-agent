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
FOLLOWUP_LIST_PATH = WIKI_ROOT / "follow-up-list.md"
INDEX_PATH = WIKI_ROOT / "index.md"
FOLLOWUP_CHECK_PROMPT = """Does this update contain a future commitment or promise
(something the person said they WILL do, with or without a deadline)?
UPDATE: {update}
Respond ONLY with valid JSON, no explanation:
If there IS a commitment:
{{"has_commitment": true, "task": "<short description>", "due_date": "<YYYY-MM-DD, your best estimate, default to 3 days from today if unclear>"}}
If there is NO commitment (just a status report of completed/ongoing work):
{{"has_commitment": false, "task": null, "due_date": null}}
TODAY'S DATE: {today}"""
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
def _detect_and_log_followup(person_name: str, update_content: str, source_file: str):
    client = get_llm_client()
    today = str(date.today())
    raw = safe_completion(
        client,
        model="deepseek/deepseek-v4-flash",
        messages=[{"role": "user", "content": FOLLOWUP_CHECK_PROMPT.format(update=update_content, today=today)}],
        max_tokens=200,
        temperature=0,
    )
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    import json
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not parsed.get("has_commitment"):
        return
    fu_id = _next_followup_id()
    task = parsed.get("task", "unspecified")
    due = parsed.get("due_date", today)
    row = f"| {fu_id} | {person_name} | {task} | {today} | {due} | {source_file} | open |\n"
    with open(FOLLOWUP_LIST_PATH, "a", encoding="utf-8") as f:
        f.write(row)
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
    if update_content:
        _detect_and_log_followup(person_name, update_content, rel_path)
    response = f"Wiki updated for {person_name}."
    if linked_projects:
        response += f" (linked to project: {', '.join(linked_projects)})"
    return {"final_response": response}
