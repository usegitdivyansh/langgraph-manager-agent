"""
Agent state: the typed dictionary that flows through every node in the graph.

Each node reads fields from this state and returns a partial update (a dict
containing only the fields it changed). LangGraph merges those updates back
into the state automatically.

All fields are Optional because nodes set them progressively as the run
proceeds — at the start of a run only the input fields are populated.
"""

from typing import TypedDict, Optional, Literal


class AgentState(TypedDict, total=False):
    # --- Input (set once at the start of every run) ---
    raw_text: str
    sender: str
    channel: str
    thread_ts: Optional[str]

    # --- Set by classify node ---
    intent: Literal["write", "query"]
    intern_name: Optional[str]
    target_interns: Optional[list[str]]
    update_content: Optional[str]
    question: Optional[str]

    # --- Set by tool / wiki-resolution nodes ---
    doc_ids: list[str]
    doc_contents: dict[str, str]
    is_new_intern: bool

    # --- Set by LLM nodes (merge / answer) ---
    draft: str

    # --- Set by reflect node ---
    reflection_verdict: Literal["pass", "fail"]
    reflection_reason: Optional[str]
    retry_count: int

    # --- Final output ---
    final_response: str