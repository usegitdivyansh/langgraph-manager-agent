"""
project_wiki -- local-filesystem storage for project pages.
Mirrors local_wiki.py's people logic: fuzzy resolution, atomic writes, and a
DETERMINISTIC roster (## People section) so collaboration queries are reliable.
Also provides deterministic detection of which known project an update mentions.
"""
import os
import re
import uuid
from pathlib import Path
from thefuzz import fuzz
from src.tools.local_wiki import WIKI_ROOT
PROJECTS_DIR = WIKI_ROOT / "projects"
FUZZY_MATCH_THRESHOLD = 80
_STOPWORDS = {"the", "a", "an", "project", "task", "work", "on", "of", "for", "skill", "our"}
PROJECT_STUB = """---
title: {name}
created: {date}
updated: {date}
type: project
status: active
---
## Summary
(no summary yet)
## People
## History
"""
def list_project_files() -> dict[str, Path]:
    if not PROJECTS_DIR.exists():
        return {}
    result = {}
    for path in PROJECTS_DIR.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        m = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
        title = m.group(1).strip() if m else path.stem
        result[title] = path
    return result
def known_project_names() -> list[str]:
    return list(list_project_files().keys())
def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}
def detect_mentioned_projects(update_text: str) -> list[str]:
    """Deterministically find which KNOWN projects are explicitly mentioned.
    A project matches if ALL significant words of its title appear in the update."""
    update_words = _significant_words(update_text)
    matched = []
    for title in list_project_files().keys():
        title_words = _significant_words(title)
        if title_words and title_words.issubset(update_words):
            matched.append(title)
    return matched
def resolve_project_file(name: str) -> tuple[str, Path, bool]:
    existing = list_project_files()
    best_match = None
    best_score = 0
    for existing_name in existing:
        score = fuzz.token_set_ratio(name.lower(), existing_name.lower())
        if score > best_score:
            best_score = score
            best_match = existing_name
    if best_match and best_score >= FUZZY_MATCH_THRESHOLD:
        return best_match, existing[best_match], False
    normalized = name.strip().lower().replace(" ", "-")
    new_path = PROJECTS_DIR / f"{normalized}.md"
    return name.strip(), new_path, True
def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
def create_project_file(name: str, path: Path) -> None:
    from datetime import date
    content = PROJECT_STUB.format(name=name, date=str(date.today()))
    _atomic_write(path, content)
def add_person_to_project(project_name: str, person_name: str) -> str:
    matched_title, path, is_new = resolve_project_file(project_name)
    if is_new:
        create_project_file(matched_title, path)
    content = path.read_text(encoding="utf-8")
    person_link = f"[[people/{person_name.lower()}]]"
    if person_link in content:
        return str(path.relative_to(WIKI_ROOT)).replace("\\", "/")
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "## People":
            lines.insert(i + 1, f"- {person_link}")
            break
    else:
        lines.append("## People")
        lines.append(f"- {person_link}")
    _atomic_write(path, "\n".join(lines) + "\n")
    return str(path.relative_to(WIKI_ROOT)).replace("\\", "/")
def get_project_people(project_name: str) -> list[str]:
    matched_title, path, is_new = resolve_project_file(project_name)
    if is_new or not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    return re.findall(r"\[\[people/([^\]]+)\]\]", content)
