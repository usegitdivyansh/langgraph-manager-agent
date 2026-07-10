"""
followup_update -- deterministic close/reopen of follow-up rows.
NO LLM here. Row selection and file writing are pure Python.
Reuses the canonical parser/serializer from followup_detect so the table
format lives in exactly one place.
"""
import os
import uuid
from pathlib import Path
from src.tools.local_wiki import WIKI_ROOT
from src.tools.followup_detect import _parse_followup_rows, _row_to_line
FOLLOWUP_LIST_PATH = WIKI_ROOT / "follow-up-list.md"
def get_open_rows_for_person(person_name: str) -> list[dict]:
    """Return all rows with status == 'open' belonging to person_name (case-insensitive)."""
    if not FOLLOWUP_LIST_PATH.exists():
        return []
    content = FOLLOWUP_LIST_PATH.read_text(encoding="utf-8")
    rows = _parse_followup_rows(content)
    target = person_name.strip().lower()
    return [
        r for r in rows
        if r["status"].lower() == "open" and r["person"].strip().lower() == target
    ]
def find_duplicate_open_row(person_name: str, task: str) -> dict | None:
    """Return an existing OPEN row for this person whose task text is identical
    (case-insensitive, whitespace-stripped), or None.
    Exact match only -- no fuzzy matching. A near-miss silently merging two
    genuinely different tasks is worse than one redundant row."""
    if not task:
        return None
    target = task.strip().lower()
    for row in get_open_rows_for_person(person_name):
        if row["task"].strip().lower() == target:
            return row
    return None
def close_followup_by_id(fu_id: str) -> bool:
    """Set status to 'done' for the row with this exact ID. Atomic write.
    Returns True if a row was changed, False otherwise."""
    if not FOLLOWUP_LIST_PATH.exists():
        return False
    content = FOLLOWUP_LIST_PATH.read_text(encoding="utf-8")
    lines = content.splitlines()
    changed = False
    new_lines = []
    for line in lines:
        if not line.startswith("|"):
            new_lines.append(line)
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 7 or cells[0] in ("ID", "---"):
            new_lines.append(line)
            continue
        if cells[0] == fu_id and cells[6].lower() == "open":
            row = {
                "id": cells[0], "person": cells[1], "task": cells[2],
                "assigned": cells[3], "due": cells[4], "source": cells[5],
                "status": "done",
            }
            new_lines.append(_row_to_line(row))
            changed = True
        else:
            new_lines.append(line)
    if not changed:
        return False
    new_content = "\n".join(new_lines)
    if not new_content.endswith("\n"):
        new_content += "\n"
    temp_path = FOLLOWUP_LIST_PATH.parent / f".follow-up-list.{uuid.uuid4().hex}.tmp"
    try:
        temp_path.write_text(new_content, encoding="utf-8")
        os.replace(temp_path, FOLLOWUP_LIST_PATH)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return True
def close_single_open_followup(person_name: str) -> str | None:
    """Deterministic rule: if the person has EXACTLY ONE open row, close it.
    Zero rows  -> None (nothing to close).
    2+ rows    -> None (ambiguous; fail safe, do nothing).
    Returns the closed FU id, or None."""
    open_rows = get_open_rows_for_person(person_name)
    if len(open_rows) != 1:
        return None
    fu_id = open_rows[0]["id"]
    if close_followup_by_id(fu_id):
        return fu_id
    return None
