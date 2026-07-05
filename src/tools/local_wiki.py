"""
local_wiki -- local-filesystem storage for the Writing skill.
Atomic writes, sha256 hash-gating, fuzzy name resolution, and deterministic
wikilink insertion (LLM output is unreliable for links, so Python guarantees them).
"""
import hashlib
import os
import re
import uuid
from pathlib import Path
from thefuzz import fuzz
WIKI_ROOT = Path(__file__).parent.parent.parent / "wiki"
PEOPLE_DIR = WIKI_ROOT / "people"
FUZZY_MATCH_THRESHOLD = 80
PERSON_STUB = """---
title: {name}
created: {date}
updated: {date}
type: entity
tags: [intern]
---
## Summary
(no summary yet)
## History
"""
def list_person_files() -> dict[str, Path]:
    if not PEOPLE_DIR.exists():
        return {}
    result = {}
    for path in PEOPLE_DIR.glob("*.md"):
        result[path.stem.capitalize()] = path
    return result
def known_person_names() -> list[str]:
    """Return the display names (capitalized file stems) of all known people."""
    return list(list_person_files().keys())
def resolve_person_file(name: str) -> tuple[str, Path, bool]:
    existing = list_person_files()
    best_match = None
    best_score = 0
    for existing_name in existing:
        score = fuzz.ratio(name.lower(), existing_name.lower())
        if score > best_score:
            best_score = score
            best_match = existing_name
    if best_match and best_score >= FUZZY_MATCH_THRESHOLD:
        return best_match, existing[best_match], False
    normalized = name.strip().lower().replace(" ", "-")
    new_path = PEOPLE_DIR / f"{normalized}.md"
    return name.strip(), new_path, True
def apply_wikilinks(body: str, self_name: str, known_people: list[str]) -> str:
    """
    Deterministically wrap known teammate names in [[people/<name>]] wikilinks.
    - Only links names in known_people (real files exist -> never a dead link).
    - Skips the page owner (self_name) so a page never links to itself.
    - Skips names already inside an existing [[...]] wikilink (no double-linking).
    - Word-boundary, case-insensitive matching (won't match inside larger words).
    Pass the BODY only (frontmatter split off), so title:/tags: never get linked.
    """
    # Protect existing wikilinks with placeholders so we don't double-wrap them
    existing_links = re.findall(r"\[\[[^\]]+\]\]", body)
    placeholders = {}
    for i, link in enumerate(existing_links):
        ph = f"\x00LINK{i}\x00"
        placeholders[ph] = link
        body = body.replace(link, ph, 1)
    for name in known_people:
        if name.lower() == (self_name or "").lower():
            continue
        pattern = re.compile(rf"\b({re.escape(name)})\b", re.IGNORECASE)
        body = pattern.sub(f"[[people/{name.lower()}]]", body)
    for ph, link in placeholders.items():
        body = body.replace(ph, link)
    return body
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
def create_person_file(name: str, path: Path) -> None:
    from datetime import date
    content = PERSON_STUB.format(name=name, date=str(date.today()))
    _atomic_write(path, content)
def read_person_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
def write_person_file(path: Path, content: str) -> None:
    _atomic_write(path, content)
def _strip_frontmatter(content: str) -> str:
    match = re.match(r"^---\n.*?\n---\n(.*)", content, re.DOTALL)
    return match.group(1) if match else content
def compute_hash(raw_content: str) -> str:
    body = _strip_frontmatter(raw_content)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
def has_content_changed(stored_hash: str | None, new_raw_content: str) -> bool:
    if stored_hash is None:
        return True
    return compute_hash(new_raw_content) != stored_hash
