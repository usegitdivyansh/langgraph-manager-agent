"""
QueryingState: the typed dictionary that flows through the Querying skill's graph.
Querying only ever reads -- no write-related fields here.
"""
from typing import TypedDict, Optional, Literal
class QueryingState(TypedDict, total=False):
    # --- Input ---
    raw_text: str
    sender: str
    channel: str
    thread_ts: Optional[str]
    # --- Set by classify node ---
    target_person: Optional[str]
    target_project: Optional[str]
    date_str: Optional[str]
    question_type: Literal["list_people", "collaborators", "status", "activity_on_date", "activity_general", "open_items"]
    # --- Set during the hop search ---
    trace: list[str]
    answer_raw: Optional[str]
    answer_source: Optional[str]
    # --- Final output ---
    final_response: str
