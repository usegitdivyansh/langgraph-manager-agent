"""
followup_detect -- Follow-up skill's detect-only logic.
Reads follow-up-list.md, categorizes each open item by due date, produces a report.
Read-only: never modifies follow-up-list.md or contacts anyone. Per Anurag's spec,
this is a cron-style skill, not a live Slack-triggered one.
"""
from datetime import date, datetime
from pathlib import Path
from src.tools.local_wiki import WIKI_ROOT
FOLLOWUP_LIST_PATH = WIKI_ROOT / "follow-up-list.md"
def _parse_followup_rows(content: str) -> list[dict]:
    """Parse the markdown table into a list of row dicts. Skips header/separator lines."""
    rows = []
    lines = content.splitlines()
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 7:
            continue
        if cells[0] in ("ID", "---"):
            continue
        rows.append({
            "id": cells[0],
            "person": cells[1],
            "task": cells[2],
            "assigned": cells[3],
            "due": cells[4],
            "source": cells[5],
            "status": cells[6],
        })
    return rows
def _categorize(row: dict, today: date) -> str:
    """Returns 'overdue', 'due_today', 'upcoming', or 'unparseable_date'."""
    try:
        due_date = datetime.strptime(row["due"], "%Y-%m-%d").date()
    except ValueError:
        return "unparseable_date"
    if due_date < today:
        return "overdue"
    if due_date == today:
        return "due_today"
    return "upcoming"
def detect_followups(today: date | None = None) -> dict:
    """
    Reads follow-up-list.md, returns open items grouped by category.
    Does NOT modify the file or contact anyone -- detect-only.
    """
    if today is None:
        today = date.today()
    if not FOLLOWUP_LIST_PATH.exists():
        return {"overdue": [], "due_today": [], "upcoming": [], "unparseable_date": [], "error": "follow-up-list.md not found"}
    content = FOLLOWUP_LIST_PATH.read_text(encoding="utf-8")
    all_rows = _parse_followup_rows(content)
    open_rows = [r for r in all_rows if r["status"].lower() == "open"]
    result = {"overdue": [], "due_today": [], "upcoming": [], "unparseable_date": []}
    for row in open_rows:
        category = _categorize(row, today)
        result[category].append(row)
    return result
def format_report(categorized: dict) -> str:
    """Formats the categorized follow-ups into a readable Slack-friendly report."""
    lines = []
    if categorized.get("error"):
        return f":warning: {categorized['error']}"
    overdue = categorized.get("overdue", [])
    due_today = categorized.get("due_today", [])
    upcoming = categorized.get("upcoming", [])
    if not overdue and not due_today and not upcoming:
        return "No open follow-up items. Everything's clear."
    if overdue:
        lines.append("*Overdue:*")
        for r in overdue:
            lines.append(f"  - [{r['id']}] {r['person']}: {r['task']} (was due {r['due']})")
    if due_today:
        lines.append("*Due today:*")
        for r in due_today:
            lines.append(f"  - [{r['id']}] {r['person']}: {r['task']}")
    if upcoming:
        lines.append("*Upcoming:*")
        for r in upcoming:
            lines.append(f"  - [{r['id']}] {r['person']}: {r['task']} (due {r['due']})")
    return "\n".join(lines)
def _row_to_line(r: dict) -> str:
    """Rebuild a table row line from a parsed row dict (same 7-column format)."""
    return f"| {r['id']} | {r['person']} | {r['task']} | {r['assigned']} | {r['due']} | {r['source']} | {r['status']} |"
def purge_expired_followups(today: date | None = None) -> int:
    """Delete follow-up rows whose due date is strictly BEFORE today (1-day grace:
    an item due on the 7th survives the 7th, is removed on the 8th's run).
    Rows with today's date, future dates, or unparseable dates are kept.
    Header is preserved. Atomic write. Returns count of rows removed.
    Intended to run on the cron pass only -- never on live queries."""
    import os
    import uuid
    if today is None:
        today = date.today()
    if not FOLLOWUP_LIST_PATH.exists():
        return 0
    content = FOLLOWUP_LIST_PATH.read_text(encoding="utf-8")
    lines = content.splitlines()
    kept_lines = []
    removed = 0
    for line in lines:
        # Keep any non-data line (header, separator, blank) untouched
        if not line.startswith("|"):
            kept_lines.append(line)
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 7 or cells[0] in ("ID", "---"):
            kept_lines.append(line)  # header/separator row -> keep
            continue
        # Data row: completed items are dropped regardless of due date
        if cells[6].lower() == "done":
            removed += 1
            continue
        # Otherwise decide by due date
        try:
            due_date = datetime.strptime(cells[4], "%Y-%m-%d").date()
        except ValueError:
            kept_lines.append(line)  # unparseable date -> keep (safe)
            continue
        if due_date < today:
            removed += 1  # strictly before today -> drop
        else:
            kept_lines.append(line)  # today or future -> keep
    if removed == 0:
        return 0
    new_content = "\n".join(kept_lines)
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
    return removed
