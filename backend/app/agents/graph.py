"""
Assembles the review nodes into a LangGraph StateGraph.

    START
      |
      v
  fetch_diff
      |
      v
  retrieve_context
      |
      v
  static_analysis
      |
      v
  llm_review            <-- conditionally skipped if no LLM provider/config
      |
      v
  validate_findings
      |
      v
  filter_and_summarize
      |
      v
     END

This mirrors the "Agent Workflow" section of the project spec. The
graph is intentionally linear (no branching search) because the review
task itself doesn't need dynamic re-planning -- what *is* agentic here is
that each node decides, based on state, whether it has useful work to do
(e.g. `llm_review_node` no-ops cleanly with no key configured, and
`static_analysis_node` only runs Semgrep on files that exist on disk).
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    fetch_diff_node,
    filter_and_summarize_node,
    llm_review_node,
    retrieve_context_node,
    static_analysis_node,
    validate_findings_node,
)
from app.agents.state import AgentState
from app.models.finding import Finding, ReviewResult, ReviewStatus


def build_review_graph():
    graph = StateGraph(AgentState)

    graph.add_node("fetch_diff", fetch_diff_node)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("static_analysis", static_analysis_node)
    graph.add_node("llm_review", llm_review_node)
    graph.add_node("validate_findings", validate_findings_node)
    graph.add_node("filter_and_summarize", filter_and_summarize_node)

    graph.add_edge(START, "fetch_diff")
    graph.add_edge("fetch_diff", "retrieve_context")
    graph.add_edge("retrieve_context", "static_analysis")
    graph.add_edge("static_analysis", "llm_review")
    graph.add_edge("llm_review", "validate_findings")
    graph.add_edge("validate_findings", "filter_and_summarize")
    graph.add_edge("filter_and_summarize", END)

    return graph.compile()


_COMPILED_GRAPH = None


def get_compiled_graph():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_review_graph()
    return _COMPILED_GRAPH


def run_agent_review(
    repo_path: str,
    diff_text: str,
    min_confidence: float | None = None,
    use_llm: bool = True,
) -> ReviewResult:
    """
    Public entrypoint: run the full LangGraph agent review and return a
    ReviewResult, using the exact same output contract as
    app.services.review_engine.run_review() so callers (CLI, API,
    webhook handler) don't need to know which pipeline produced it.
    """
    graph = get_compiled_graph()
    initial_state: AgentState = {
        "repo_path": repo_path,
        "diff_text": diff_text,
        "use_llm": use_llm,
    }
    if min_confidence is not None:
        initial_state["min_confidence"] = min_confidence

    final_state = graph.invoke(initial_state)

    findings = [Finding(**f) for f in final_state.get("final_findings", [])]
    return ReviewResult(
        status=ReviewStatus.COMPLETED,
        files_reviewed=final_state.get("files_reviewed", []),
        findings=findings,
        summary=final_state.get("summary", ""),
    )
