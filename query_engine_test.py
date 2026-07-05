"""
Prototype of the Querying skill's 5-hop fallback logic.
Hop order: index.md -> person page -> wikilinks -> raw minutes -> raw transcript.
Stops at the first hop that contains an answer.
"""

import re
from pathlib import Path

WIKI_ROOT = Path(__file__).parent / "wiki"

WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def read_file(rel_path: str) -> str | None:
    """Read a wiki file by its relative path (no .md needed). Returns None if missing."""
    path = WIKI_ROOT / f"{rel_path}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def find_person_file(index_content: str, person_name: str) -> str | None:
    """Hop 1: search index.md's People table for a matching row."""
    for line in index_content.splitlines():
        if line.startswith("|") and person_name.lower() in line.lower():
            parts = [p.strip() for p in line.split("|")]
            for part in parts:
                if part.endswith(".md"):
                    return part[:-3]
    return None


def extract_wikilinks(content: str) -> list[str]:
    return WIKILINK_PATTERN.findall(content)


def has_date_entry(content: str, date_str: str) -> str | None:
    """Look for a '### <date>' History heading and return that section's text."""
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


def query_activity_on_date(person: str, date_str: str) -> dict:
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
    trace.append(f"Hop 4 (raw/minutes/{date_str}.md): " + ("not found" if minutes_content is None else "no mention of person"))

    transcript_content = read_file(f"raw/transcripts/{date_str}")
    if transcript_content and person.lower() in transcript_content.lower():
        trace.append(f"Hop 5 (raw/transcripts/{date_str}.md): person mentioned")
        return {"answer": transcript_content, "trace": trace, "source": f"raw/transcripts/{date_str}.md"}
    trace.append(f"Hop 5 (raw/transcripts/{date_str}.md): " + ("not found" if transcript_content is None else "no mention of person"))

    return {"answer": None, "trace": trace, "source": None}


if __name__ == "__main__":
    result = query_activity_on_date("Divyansh", "2026-06-26")
    print("=== QUERY: what did Divyansh do on 2026-06-26 ===\n")
    for step in result["trace"]:
        print(" -", step)
    print()
    if result["answer"]:
        print(f"ANSWER FOUND (source: {result['source']}):\n{result['answer']}")
    else:
        print("NO RECORD FOUND for that date.")