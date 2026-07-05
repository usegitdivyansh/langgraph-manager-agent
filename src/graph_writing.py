"""
graph_writing -- assembles the Writing skill as a compiled LangGraph.
classify -> resolve_person -> read_person_file -> merge -> reflect -> [retry merge | commit].
Guards against unidentifiable person_name and validates every merge via reflect.
"""
from langgraph.graph import StateGraph, END
from src.agent.writing_state import WritingState
from src.agent.classify_write import classify_write_message
from src.agent.merge_write import merge_write
from src.agent.reflect_write import reflect_write
from src.agent.commit_write import commit_write
from src.tools.local_wiki import resolve_person_file, read_person_file
MAX_RETRIES = 2
def node_classify(state: WritingState) -> dict:
    result = classify_write_message(state)
    result["retry_count"] = state.get("retry_count") or 0
    return result
def node_resolve_person(state: WritingState) -> dict:
    person_name = state.get("person_name") or ""
    if not person_name.strip():
        return {
            "person_name": None,
            "person_file_path": None,
            "is_new_person": False,
        }
    name, path, is_new = resolve_person_file(person_name)
    return {
        "person_name": name,
        "person_file_path": str(path),
        "is_new_person": is_new,
    }
def node_read_person_file(state: WritingState) -> dict:
    from pathlib import Path
    path_str = state.get("person_file_path")
    if not path_str:
        return {"current_wiki_content": None}
    content = read_person_file(Path(path_str))
    return {"current_wiki_content": content}
def node_merge(state: WritingState) -> dict:
    if not state.get("person_file_path"):
        return {"draft": None}
    return merge_write(state)
def node_reflect(state: WritingState) -> dict:
    if not state.get("person_file_path"):
        return {"reflection_verdict": "pass", "reflection_reason": None}
    return reflect_write(state)
def node_commit(state: WritingState) -> dict:
    if not state.get("person_file_path"):
        return {"final_response": "Could not identify who this update is about -- no wiki was updated."}
    verdict = state.get("reflection_verdict", "pass")
    retry_count = state.get("retry_count", 0)
    if verdict == "fail" and retry_count >= MAX_RETRIES:
        result = commit_write(state)
        result["final_response"] = (
            result.get("final_response", "") +
            " (Warning: committed after failed quality checks -- please review this entry manually.)"
        )
        return result
    return commit_write(state)
def route_after_reflect(state: WritingState) -> str:
    if not state.get("person_file_path"):
        return "commit"
    verdict = state.get("reflection_verdict", "pass")
    retry_count = state.get("retry_count", 0)
    if verdict == "pass":
        return "commit"
    if retry_count < MAX_RETRIES:
        return "merge"
    return "commit"
def build_writing_graph():
    graph = StateGraph(WritingState)
    graph.add_node("classify", node_classify)
    graph.add_node("resolve_person", node_resolve_person)
    graph.add_node("read_person_file", node_read_person_file)
    graph.add_node("merge", node_merge)
    graph.add_node("reflect", node_reflect)
    graph.add_node("commit", node_commit)
    graph.set_entry_point("classify")
    graph.add_edge("classify", "resolve_person")
    graph.add_edge("resolve_person", "read_person_file")
    graph.add_edge("read_person_file", "merge")
    graph.add_edge("merge", "reflect")
    graph.add_conditional_edges("reflect", route_after_reflect, {
        "merge": "merge",
        "commit": "commit",
    })
    graph.add_edge("commit", END)
    return graph.compile()
writing_agent = build_writing_graph()
