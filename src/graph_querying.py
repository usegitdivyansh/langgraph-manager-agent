"""
graph_querying -- assembles the Querying skill as a compiled LangGraph.
classify -> search (dispatches by question_type) -> format_answer.
"""
from langgraph.graph import StateGraph, END
from src.agent.querying_state import QueryingState
from src.agent.classify_query import classify_query_message
from src.tools.hop_search import (
    search_activity_on_date,
    search_activity_general,
    search_list_people,
    search_open_items,
    search_collaborators,
    search_status,
)
def node_classify(state: QueryingState) -> dict:
    return classify_query_message(state)
def node_search(state: QueryingState) -> dict:
    question_type = state.get("question_type", "activity_general")
    person = state.get("target_person") or ""
    project = state.get("target_project") or ""
    date_str = state.get("date_str") or ""
    print(f"\n[DISPATCH] question_type={question_type} person={person!r} project={project!r} date={date_str!r}")
    if question_type == "activity_on_date" and date_str:
        result = search_activity_on_date(person, date_str)
    elif question_type == "activity_general":
        result = search_activity_general(person)
    elif question_type == "list_people":
        result = search_list_people(project or person)
    elif question_type == "collaborators":
        result = search_collaborators(person)
    elif question_type == "open_items":
        result = search_open_items(person)
    elif question_type == "status":
        result = search_status(person, project)
    else:
        result = {"answer": None, "trace": [f"unknown question_type: {question_type}"], "source": None}
    print(f"[RESULT] source={result.get('source')} trace={result.get('trace')}")
    return {
        "trace": result.get("trace", []),
        "answer_raw": result.get("answer"),
        "answer_source": result.get("source"),
    }
def node_format_answer(state: QueryingState) -> dict:
    answer_raw = state.get("answer_raw")
    source = state.get("answer_source")
    if answer_raw:
        response = f"{answer_raw.strip()}\n\n_(source: {source})_"
    else:
        subject = state.get("target_person") or state.get("target_project") or "that"
        response = f"No record found for '{subject}'. Checked the wiki, linked pages, and available raw sources."
    return {"final_response": response}
def build_querying_graph():
    graph = StateGraph(QueryingState)
    graph.add_node("classify", node_classify)
    graph.add_node("search", node_search)
    graph.add_node("format_answer", node_format_answer)
    graph.set_entry_point("classify")
    graph.add_edge("classify", "search")
    graph.add_edge("search", "format_answer")
    graph.add_edge("format_answer", END)
    return graph.compile()
querying_agent = build_querying_graph()
