"""
Google Drive tools — dynamic intern roster management.
Talks to Drive to list, fuzzy-match, and create intern wiki docs.
No LLM logic here.
"""

import os
from googleapiclient.discovery import build
from thefuzz import process as fuzz_process
from src.tools.google_docs import get_credentials

WIKI_TEMPLATE = """# {name}

## Summary

(No updates yet.)

## History

## Projects

## Notes
"""


def get_drive_service():
    creds = get_credentials()
    return build("drive", "v3", credentials=creds)


def list_intern_docs() -> dict[str, str]:
    """
    List all Google Docs in the Intern Wikis folder.
    Returns dict of {intern_name: doc_id}.
    Doc title must be exactly the intern's name (e.g. "Harshit", "Riya").
    """
    folder_id = os.environ["INTERN_WIKIS_FOLDER_ID"]
    service = get_drive_service()

    results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false",
        fields="files(id, name)",
    ).execute()

    files = results.get("files", [])
    return {f["name"].strip(): f["id"] for f in files}


def resolve_intern_doc(name: str) -> tuple[str | None, str | None, bool]:
    """
    Fuzzy-match intern name against the roster.
    Returns (matched_name, doc_id, is_new_intern).
    If score >= 80: existing intern matched.
    If score < 80: treat as new intern.
    """
    roster = list_intern_docs()

    if not roster:
        return None, None, True

    name_clean = name.strip().title()

    best_match, score = fuzz_process.extractOne(name_clean, roster.keys())

    if score >= 80:
        return best_match, roster[best_match], False
    else:
        return name_clean, None, True


def create_intern_doc(name: str) -> str:
    """
    Create a new Google Doc for a new intern in the Intern Wikis folder.
    Seeds it with the wiki template.
    Returns the new doc_id.
    """
    folder_id = os.environ["INTERN_WIKIS_FOLDER_ID"]
    drive_service = get_drive_service()

    # Create the doc in the folder
    file_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id],
    }
    created = drive_service.files().create(
        body=file_metadata,
        fields="id",
    ).execute()

    doc_id = created["id"]

    # Seed with template
    from src.tools.google_docs import overwrite_doc
    overwrite_doc(doc_id, WIKI_TEMPLATE.format(name=name))

    return doc_id