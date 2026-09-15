"""
Node functions for the review agent graph.

Each function takes the current AgentState and returns a partial-state
dict that LangGraph merges in. Keeping nodes as small, single-purpose,
pure-ish functions (side effects limited to logging + the tools they
explicitly call) is what makes this "agentic but not needlessly complex"
per the project's Important Engineering Rule.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.state import AgentState
from app.analysis.rule_based_checks import run_rule_based_checks
from app.analysis.semgrep_runner import run_semgrep_for_diffs
from app.analysis.testing_checks import check_missing_tests
from app.config import settings
from app.llm.base import LLMError
from app.llm.factory import get_llm_provider
from app.models.finding import Finding
from app.services.diff_parser import parse_diff
from app.services.repo_reader import RepositoryReader
from app.services.validator import validate_findings

logger = logging.getLogger("agents.nodes")


def fetch_diff_node(state: AgentState) -> Dict[str, Any]:
    """Parse the raw diff text into per-file structured diffs."""
    file_diffs = parse_diff(state["diff_text"])
    files_reviewed = list(file_diffs.keys())[: settings.max_files_per_review]
    logger.info("agent.fetch_diff", extra={"file_count": len(files_reviewed)})
    return {"file_diffs": file_diffs, "files_reviewed": files_reviewed}


def retrieve_context_node(state: AgentState) -> Dict[str, Any]:
    """Read each changed file's current content for surrounding context."""
    repo_context: Dict[str, str] = {}
    try:
        reader = RepositoryReader(state["repo_path"])
    except FileNotFoundError:
        logger.warning("agent.repo_not_found", extra={"repo_path": state["repo_path"]})
        return {"repo_context": {}}

    for path in state["files_reviewed"]:
        content = reader.read_file(path)
        if content:
            repo_context[path] = content
    return {"repo_context": repo_context}


def static_analysis_node(state: AgentState) -> Dict[str, Any]:
    """Run deterministic checks: rule-based patterns + Semgrep + missing-tests heuristic."""
    file_diffs = state["file_diffs"]
    files_reviewed = state["files_reviewed"]
    repo_context = state.get("repo_context", {})

    findings: list[Finding] = []
    for path in files_reviewed:
        file_diff = file_diffs[path]
        content = repo_context.get(path)
        findings.extend(run_rule_based_checks(file_diff, content))

    # Semgrep runs once across all changed files (real files on disk when
    # available, reconstructed from added lines otherwise).
    try:
        reader = RepositoryReader(state["repo_path"])
        reviewed_file_diffs = {path: file_diffs[path] for path in files_reviewed}
        findings.extend(run_semgrep_for_diffs(reviewed_file_diffs, repo_reader=reader))
    except FileNotFoundError:
        reviewed_file_diffs = {path: file_diffs[path] for path in files_reviewed}
        findings.extend(run_semgrep_for_diffs(reviewed_file_diffs, repo_reader=None))

    # Missing-tests heuristic.
    touched_test_files = any(
        p.rsplit("/", 1)[-1].startswith("test_") or p.endswith("_test.py") for p in files_reviewed
    )
    try:
        reader = RepositoryReader(state["repo_path"])

        def _existing_tests_reference(func_name: str) -> bool:
            try:
                matches = reader.search_repository(func_name, max_results=1)
                return len(matches) > 0
            except Exception:
                return False

    except FileNotFoundError:
        def _existing_tests_reference(func_name: str) -> bool:
            return False

    for path in files_reviewed:
        findings.extend(
            check_missing_tests(file_diffs[path], touched_test_files, _existing_tests_reference)
        )

    logger.info("agent.static_analysis", extra={"finding_count": len(findings)})
    return {"static_findings": [f.model_dump(mode="json") for f in findings]}


def llm_review_node(state: AgentState) -> Dict[str, Any]:
    """Run the LLM reviewer over each changed file, if a provider is configured."""
    if not state.get("use_llm", True):
        return {"llm_findings": []}

    llm_provider = get_llm_provider()
    if llm_provider is None:
        logger.info("agent.llm_not_configured")
        return {"llm_findings": []}

    file_diffs = state["file_diffs"]
    repo_context = state.get("repo_context", {})
    llm_findings = []

    for path in state["files_reviewed"]:
        file_diff = file_diffs[path]
        diff_hunk = "\n".join(f"+{al.content}" for al in file_diff.added_lines)
        if not diff_hunk.strip():
            continue
        try:
            raw = llm_provider.generate_review(path, diff_hunk, context=repo_context.get(path, ""))
        except LLMError as exc:
            logger.warning("agent.llm_review_failed", extra={"file": path, "error": str(exc)})
            continue
        for item in raw:
            item.setdefault("source", "llm")
            item.setdefault("file", path)
            llm_findings.append(item)

    logger.info("agent.llm_review", extra={"finding_count": len(llm_findings)})
    return {"llm_findings": llm_findings}


def validate_findings_node(state: AgentState) -> Dict[str, Any]:
    """Run every candidate finding (static + LLM) through the validator."""
    all_raw = state.get("static_findings", []) + state.get("llm_findings", [])
    findings: list[Finding] = []
    for raw in all_raw:
        try:
            findings.append(Finding(**raw))
        except Exception as exc:
            logger.warning("agent.malformed_finding", extra={"error": str(exc)})

    llm_provider = get_llm_provider() if state.get("use_llm", True) else None
    diff_context_by_file = {
        path: "\n".join(f"+{al.content}" for al in fd.added_lines)
        for path, fd in state["file_diffs"].items()
    }
    validated = validate_findings(findings, diff_context_by_file, llm_provider)
    logger.info("agent.validate_findings", extra={"kept": len(validated), "total": len(findings)})
    return {"validated_findings": [f.model_dump(mode="json") for f in validated]}


def filter_and_summarize_node(state: AgentState) -> Dict[str, Any]:
    """Filter by MIN_CONFIDENCE and build the final structured review."""
    threshold = state.get("min_confidence")
    if threshold is None:
        threshold = settings.min_confidence
    validated = [Finding(**f) for f in state.get("validated_findings", [])]
    final = [f for f in validated if f.confidence >= threshold]

    files_reviewed = state["files_reviewed"]
    if not final:
        summary = f"Reviewed {len(files_reviewed)} changed file(s). No high-confidence issues found."
    else:
        by_sev: Dict[str, int] = {}
        for f in final:
            by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
        sev_str = ", ".join(f"{c} {s}" for s, c in sorted(by_sev.items()))
        summary = (
            f"Reviewed {len(files_reviewed)} changed file(s) and identified "
            f"{len(final)} high-confidence issue(s) ({sev_str})."
        )

    logger.info("agent.completed", extra={"final_count": len(final)})
    return {
        "final_findings": [f.model_dump(mode="json") for f in final],
        "summary": summary,
        "status": "completed",
    }
