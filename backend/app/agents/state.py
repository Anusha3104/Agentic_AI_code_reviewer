"""
Shared state that flows through every node of the review agent graph.

Kept as a TypedDict (LangGraph's preferred state shape) rather than a
Pydantic model so nodes can return partial-state dicts, which LangGraph
merges automatically.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # --- inputs ---
    repo_path: str
    diff_text: str
    min_confidence: float
    use_llm: bool
    run_tests: bool

    # --- working state, populated by nodes ---
    file_diffs: Dict[str, Any]              # path -> FileDiff
    files_reviewed: List[str]
    repo_context: Dict[str, str]            # path -> extra context string
    static_findings: List[Dict]             # rule-based + semgrep, as dicts
    llm_findings: List[Dict]
    validated_findings: List[Dict]
    test_results: Optional[Dict]

    # --- output ---
    final_findings: List[Dict]
    summary: str
    status: str
    error: Optional[str]
