"""
WritingState: the typed dictionary that flows through the Writing skill's graph.
Writing skill only ever handles updates — no query-related fields here.
"""

from typing import TypedDict, Optional, Literal


class WritingState(TypedDict, total=False):
    # --- Input (set once at the start of every run) ---
    raw_text: str
    sender: str
    channel: str
    thread_ts: Optional[str]

    # --- Set by classify node ---
    person_name: Optional[str]
    update_content: Optional[str]

    # --- Set by resolve_person node ---
    person_file_path: Optional[str]
    is_new_person: bool

    # --- Set by read_person_file node ---
    current_wiki_content: Optional[str]

    # --- Set by merge_update node ---
    draft: str

    # --- Set by reflect node ---
    reflection_verdict: Literal["pass", "fail"]
    reflection_reason: Optional[str]
    retry_count: int

    # --- Final output ---
    final_response: str