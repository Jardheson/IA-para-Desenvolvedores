from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.graph.edges import route_after_evaluate
from src.graph.nodes import (
    analyze_priority,
    analyze_request,
    bootstrap_execution,
    classify_incident,
    emit_output,
    evaluate_risk,
    finalize_normal,
    finalize_risky,
    tool_invoke,
    validate_request,
)
from src.graph.state import TriageState


def build_graph():
    g = StateGraph(TriageState)
    g.add_node("bootstrap_execution", bootstrap_execution)
    g.add_node("validate_request", validate_request)
    g.add_node("analyze_request", analyze_request)
    g.add_node("classify_incident", classify_incident)
    g.add_node("analyze_priority", analyze_priority)
    g.add_node("tool_invoke", tool_invoke)
    g.add_node("evaluate_risk", evaluate_risk)
    g.add_node("finalize_normal", finalize_normal)
    g.add_node("finalize_risky", finalize_risky)
    g.add_node("emit_output", emit_output)

    g.add_edge(START, "bootstrap_execution")
    g.add_edge("bootstrap_execution", "validate_request")
    g.add_edge("validate_request", "analyze_request")
    g.add_edge("analyze_request", "classify_incident")
    g.add_edge("analyze_request", "analyze_priority")
    g.add_edge("classify_incident", "tool_invoke")
    g.add_edge("analyze_priority", "tool_invoke")
    g.add_edge("tool_invoke", "evaluate_risk")
    g.add_conditional_edges(
        "evaluate_risk",
        route_after_evaluate,
        {"finalize_normal": "finalize_normal", "finalize_risky": "finalize_risky"},
    )
    g.add_edge("finalize_normal", "emit_output")
    g.add_edge("finalize_risky", "emit_output")
    g.add_edge("emit_output", END)

    return g.compile(checkpointer=None)


graph = build_graph()
