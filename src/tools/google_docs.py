"""
Google Docs API tools — deterministic read/write layer.
No LLM logic here. Called by graph nodes.
"""

import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

def get_credentials() -> Credentials:
    creds_path = os.environ["GOOGLE_CREDENTIALS_PATH"]
    token_path = os.path.join(os.path.dirname(creds_path), "token.json")

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds


def read_doc(doc_id: str) -> str:
    """Read full plain text content from a Google Doc."""
    creds = get_credentials()
    service = build("docs", "v1", credentials=creds)
    doc = service.documents().get(documentId=doc_id).execute()

    text = ""
    for block in doc.get("body", {}).get("content", []):
        para = block.get("paragraph", {})
        for el in para.get("elements", []):
            text += el.get("textRun", {}).get("content", "")
    return text


def overwrite_doc(doc_id: str, new_content: str) -> None:
    """
    Overwrite a Google Doc with new_content.
    Strategy: delete the entire body, then insert fresh content.
    """
    creds = get_credentials()
    service = build("docs", "v1", credentials=creds)

    doc = service.documents().get(documentId=doc_id).execute()
    body_content = doc.get("body", {}).get("content", [])

    # Find the last index of the document body
    end_index = 1
    for block in body_content:
        ei = block.get("endIndex")
        if ei:
            end_index = ei

    requests = []

    # Delete all existing content (if doc has more than 1 character)
    if end_index > 2:
        requests.append({
            "deleteContentRange": {
                "range": {
                    "startIndex": 1,
                    "endIndex": end_index - 1,
                }
            }
        })

    # Insert new content at the start
    requests.append({
        "insertText": {
            "location": {"index": 1},
            "text": new_content,
        }
    })

    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests}
    ).execute()