import re
from pathlib import Path
from src.tools.local_wiki import WIKI_ROOT
WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
_STOPWORDS = {"the", "a", "an", "project", "task", "work", "on", "of", "for", "skill"}
# Typographic Unicode characters LLMs substitute for plain ASCII, which break
# exact filename/path matching. Map them back to their ASCII equivalents.
_UNICODE_NORMALIZE = {
    "\u2011": "-",  # non-breaking hyphen
    "\u2010": "-",  # hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u00a0": " ",  # non-breaking space
}
def normalize_text(text: str) -> str:
    for bad, good in _UNICODE_NORMALIZE.items():
        text = text.replace(bad, good)
    return text
def read_file(rel_path: str) -> str | None:
    rel_path = normalize_text(rel_path)
    path = WIKI_ROOT / f"{rel_path}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", normalize_text(text).lower())
    return {w for w in words if w not in _STOPWORDS}
def _row_matches(line: str, query: str) -> bool:
    query_words = _significant_words(query)
    if not query_words:
        return False
    line_lower = normalize_text(line).lower()
    return all(w in line_lower for w in query_words)
def find_person_file(index_content: str, person_name: str) -> str | None:
    for line in index_content.splitlines():
        if line.startswith("|") and _row_matches(line, person_name):
            for part in [p.strip() for p in line.split("|")]:
                if part.endswith(".md"):
                    return part[:-3]
    return None
def find_project_file(index_content: str, project_name: str) -> str | None:
    in_section = False
    for line in index_content.splitlines():
        if line.strip().startswith("## Projects"):
            in_section = True
            continue
        if line.strip().startswith("## ") and in_section:
            break
        if in_section and line.startswith("|") and _row_matches(line, project_name):
            for part in [p.strip() for p in line.split("|")]:
                if part.endswith(".md"):
                    return part[:-3]
    return None
def extract_wikilinks(content: str) -> list[str]:
    return [normalize_text(link) for link in WIKILINK_PATTERN.findall(content)]
def extract_summary(content: str) -> str | None:
    lines = content.splitlines()
    capture = False
    captured = []
    for line in lines:
        if line.strip().startswith("## Summary"):
            capture = True
            continue
        if capture and line.strip().startswith("## "):
            break
        if capture:
            captured.append(line)
    text = "\n".join(captured).strip()
    return text if text else None
def has_date_entry(content: str, date_str: str) -> str | None:
    lines = content.splitlines()
    capture = False
    captured = []
    for line in lines:
        if line.strip().startswith("### ") and date_str in line:
            capture = True
            captured.append(line)
            continue
        if capture and line.strip().startswith("### "):
            break
        if capture:
            captured.append(line)
    return "\n".join(captured).strip() if captured else None
def search_activity_on_date(person: str, date_str: str) -> dict:
    trace = []
    index_content = read_file("index")
    if index_content is None:
        return {"answer": None, "trace": trace + ["index.md missing"], "source": None}
    person_file = find_person_file(index_content, person)
    trace.append(f"Hop 1 (index.md): found -> {person_file}" if person_file else "Hop 1 (index.md): no match")
    if not person_file:
        return {"answer": None, "trace": trace, "source": None}
    person_content = read_file(person_file)
    if person_content is None:
        trace.append(f"Hop 2 ({person_file}.md): file missing despite index entry")
        return {"answer": None, "trace": trace, "source": None}
    entry = has_date_entry(person_content, date_str)
    if entry:
        trace.append(f"Hop 2 ({person_file}.md): found entry for {date_str}")
        return {"answer": entry, "trace": trace, "source": f"{person_file}.md"}
    trace.append(f"Hop 2 ({person_file}.md): no entry for {date_str}")
    links = extract_wikilinks(person_content)
    trace.append(f"Hop 3: wikilinks found -> {links}")
    for link in links:
        linked_content = read_file(link)
        if linked_content is None:
            trace.append(f"Hop 3 ({link}.md): missing, skipped")
            continue
        entry = has_date_entry(linked_content, date_str)
        if entry:
            trace.append(f"Hop 3 ({link}.md): found entry for {date_str}")
            return {"answer": entry, "trace": trace, "source": f"{link}.md"}
        trace.append(f"Hop 3 ({link}.md): no entry for {date_str}")
    minutes_content = read_file(f"raw/minutes/{date_str}")
    if minutes_content and person.lower() in minutes_content.lower():
        trace.append(f"Hop 4 (raw/minutes/{date_str}.md): person mentioned")
        return {"answer": minutes_content, "trace": trace, "source": f"raw/minutes/{date_str}.md"}
    trace.append(f"Hop 4 (raw/minutes/{date_str}.md): " + ("not found" if minutes_content is None else "no mention"))
    transcript_content = read_file(f"raw/transcripts/{date_str}")
    if transcript_content and person.lower() in transcript_content.lower():
        trace.append(f"Hop 5 (raw/transcripts/{date_str}.md): person mentioned")
        return {"answer": transcript_content, "trace": trace, "source": f"raw/transcripts/{date_str}.md"}
    trace.append(f"Hop 5 (raw/transcripts/{date_str}.md): " + ("not found" if transcript_content is None else "no mention"))
    return {"answer": None, "trace": trace, "source": None}
def search_activity_general(person: str) -> dict:
    trace = []
    index_content = read_file("index")
    if index_content is None:
        return {"answer": None, "trace": ["index.md missing"], "source": None}
    person_file = find_person_file(index_content, person)
    trace.append(f"Hop 1 (index.md): found -> {person_file}" if person_file else "Hop 1 (index.md): no match")
    if not person_file:
        return {"answer": None, "trace": trace, "source": None}
    person_content = read_file(person_file)
    summary = extract_summary(person_content) if person_content else None
    if summary:
        trace.append(f"Hop 2 ({person_file}.md): Summary found")
        return {"answer": summary, "trace": trace, "source": f"{person_file}.md"}
    trace.append(f"Hop 2 ({person_file}.md): no Summary content")
    return {"answer": None, "trace": trace, "source": None}
def search_list_people(project: str) -> dict:
    """Return the roster (## People) of a project -- deterministic, reads wikilinks."""
    from src.tools.project_wiki import get_project_people
    trace = []
    if not project:
        return {"answer": None, "trace": ["no project specified"], "source": None}
    people = get_project_people(project)
    trace.append(f"project roster '{project}': {len(people)} person(s)")
    if not people:
        return {"answer": None, "trace": trace, "source": None}
    lines = [f"- {p.capitalize()}" for p in people]
    answer = f"People on {project}:\n" + "\n".join(lines)
    return {"answer": answer, "trace": trace, "source": "project roster"}
def search_open_items(person: str) -> dict:
    trace = []
    content = read_file("follow-up-list")
    if content is None:
        return {"answer": None, "trace": ["follow-up-list.md missing"], "source": None}
    matching_rows = [
        line for line in content.splitlines()
        if line.startswith("|") and person and person.lower() in line.lower() and "open" in line.lower()
    ]
    trace.append(f"follow-up-list.md: {len(matching_rows)} open row(s) matched for {person}")
    if matching_rows:
        return {"answer": "\n".join(matching_rows), "trace": trace, "source": "follow-up-list.md"}
    return {"answer": None, "trace": trace, "source": None}
def search_collaborators(person: str) -> dict:
    """
    Project-scoped collaborator lookup: find every project whose roster includes
    `person`, then return the OTHER people on those projects.
    Deterministic -- reads project rosters (## People sections), not LLM inference.
    """
    from src.tools.project_wiki import list_project_files, get_project_people
    trace = []
    person_lc = (person or "").lower()
    if not person_lc:
        return {"answer": None, "trace": ["no person specified"], "source": None}
    collaborators = {}  # name -> set of project titles
    source_projects = []
    for title in list_project_files().keys():
        roster = [p.lower() for p in get_project_people(title)]
        if person_lc in roster:
            source_projects.append(title)
            for other in roster:
                if other != person_lc:
                    collaborators.setdefault(other, set()).add(title)
    trace.append(f"person '{person}' found on projects: {source_projects or 'none'}")
    if not source_projects:
        return {"answer": None, "trace": trace, "source": None}
    if not collaborators:
        return {
            "answer": f"{person} is on {', '.join(source_projects)} but has no listed collaborators yet.",
            "trace": trace,
            "source": "project rosters",
        }
    lines = []
    for name, projects in sorted(collaborators.items()):
        lines.append(f"- {name.capitalize()} (on {', '.join(sorted(projects))})")
    answer = f"{person} is working with:\n" + "\n".join(lines)
    trace.append(f"found {len(collaborators)} collaborator(s)")
    return {"answer": answer, "trace": trace, "source": "project rosters"}
def search_status(person: str, project: str) -> dict:
    """
    Status lookup = current-state Summary of a project or person.
    - project set        -> project Summary  (Case B)
    - person set only    -> person Summary   (Case A)
    - both set           -> person Summary, project-filtering not yet applied (Case C fallback)
    Deterministic: reuses extract_summary + find_*_file. No LLM.
    """
    trace = []
    index_content = read_file("index")
    if index_content is None:
        return {"answer": None, "trace": ["index.md missing"], "source": None}
    # Case B: project status takes priority when a project is named alone
    if project and not person:
        project_file = find_project_file(index_content, project)
        trace.append(f"Hop 1 (index.md): project -> {project_file}" if project_file else "Hop 1 (index.md): no project match")
        if not project_file:
            return {"answer": None, "trace": trace, "source": None}
        content = read_file(project_file)
        summary = extract_summary(content) if content else None
        if summary:
            trace.append(f"Hop 2 ({project_file}.md): Summary found")
            return {"answer": summary, "trace": trace, "source": f"{project_file}.md"}
        trace.append(f"Hop 2 ({project_file}.md): no Summary content")
        return {"answer": None, "trace": trace, "source": None}
    # Case A / Case C: person status (Case C = both set -> person wins, note the limitation)
    if person:
        person_file = find_person_file(index_content, person)
        trace.append(f"Hop 1 (index.md): person -> {person_file}" if person_file else "Hop 1 (index.md): no person match")
        if not person_file:
            return {"answer": None, "trace": trace, "source": None}
        content = read_file(person_file)
        summary = extract_summary(content) if content else None
        if summary:
            if project:
                trace.append(f"Hop 2 ({person_file}.md): Summary found (note: project '{project}' filter not applied - Phase 2)")
            else:
                trace.append(f"Hop 2 ({person_file}.md): Summary found")
            return {"answer": summary, "trace": trace, "source": f"{person_file}.md"}
        trace.append(f"Hop 2 ({person_file}.md): no Summary content")
        return {"answer": None, "trace": trace, "source": None}
    trace.append("status: neither person nor project specified")
    return {"answer": None, "trace": trace, "source": None}
