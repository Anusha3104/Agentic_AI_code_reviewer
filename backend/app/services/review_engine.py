"""
Phase 1 review engine.

This is the simplest possible version of the pipeline described in
ARCHITECTURE.md:

    diff -> parse -> (repo context) -> deterministic checks -> filter -> ReviewResult

From Phase 2 onward an LLM-based analyzer, a LangGraph agent, a validation
stage, and repository-context retrieval will be layered on top of this
same shape. Nothing here should need to change structurally when that
happens -- new analyzers just contribute more `Finding` objects into the
same filtering/reporting path.
"""
from __future__ import annotations

import logging
from typing import List

from app.analysis.rule_based_checks import run_rule_based_checks
from app.analysis.semgrep_runner import run_semgrep_for_diffs
from app.analysis.testing_checks import check_missing_tests
from app.config import settings
from app.llm.base import LLMError
from app.llm.factory import get_llm_provider
from app.models.finding import Finding, ReviewResult, ReviewStatus
from app.services.diff_parser import parse_diff
from app.services.repo_reader import RepositoryReader

logger = logging.getLogger("review_engine")


def _llm_findings_for_file(llm_provider, path: str, file_diff, context: str) -> List[Finding]:
    """Call the LLM reviewer for one file and coerce its output into Finding objects."""
    diff_hunk = "\n".join(f"+{al.content}" for al in file_diff.added_lines)
    if not diff_hunk.strip():
        return []
    try:
        raw_findings = llm_provider.generate_review(path, diff_hunk, context=context)
    except LLMError as exc:
        logger.warning("review.llm_review_failed", extra={"file": path, "error": str(exc)})
        return []

    findings: List[Finding] = []
    for raw in raw_findings:
        try:
            raw.setdefault("source", "llm")
            findings.append(Finding(**raw))
        except Exception as exc:  # malformed LLM output must never crash the review
            logger.warning("review.malformed_llm_finding", extra={"file": path, "error": str(exc)})
    return findings



def _build_summary(files_reviewed: List[str], findings: List[Finding]) -> str:
    if not findings:
        return (
            f"Reviewed {len(files_reviewed)} changed file(s). "
            "No high-confidence issues found."
        )

    by_severity = {}
    for f in findings:
        by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1

    severity_summary = ", ".join(
        f"{count} {sev}" for sev, count in sorted(by_severity.items())
    )
    return (
        f"Reviewed {len(files_reviewed)} changed file(s) and identified "
        f"{len(findings)} high-confidence issue(s) ({severity_summary})."
    )


def run_review(
    repo_path: str,
    diff_text: str,
    min_confidence: float | None = None,
    use_llm: bool = True,
) -> ReviewResult:
    """
    Run a full review over a diff applied against a local repo.

    Args:
        repo_path: path to the repository the diff applies to (used for
            reading surrounding file context; falls back gracefully if a
            file isn't present, e.g. for standalone test diffs).
        diff_text: unified diff content (as produced by `git diff`).
        min_confidence: overrides the configured MIN_CONFIDENCE threshold.
        use_llm: if True (default) and an LLM provider is configured
            (GEMINI_API_KEY set), the LLM reviewer runs alongside the
            deterministic checks. If no provider is configured, this is a
            no-op -- the review still completes using only deterministic
            checks, exactly as in Phase 1.

    Returns:
        A ReviewResult containing the filtered, structured findings.
    """
    threshold = settings.min_confidence if min_confidence is None else min_confidence

    logger.info("review.started", extra={"repo_path": repo_path})

    file_diffs = parse_diff(diff_text)
    if len(file_diffs) > settings.max_files_per_review:
        logger.warning(
            "review.truncated",
            extra={"total_files": len(file_diffs), "limit": settings.max_files_per_review},
        )

    files_reviewed = list(file_diffs.keys())[: settings.max_files_per_review]

    try:
        reader = RepositoryReader(repo_path)
    except FileNotFoundError:
        reader = None
        logger.warning("review.repo_not_found", extra={"repo_path": repo_path})

    llm_provider = get_llm_provider() if use_llm else None
    if use_llm and llm_provider is None:
        logger.info("review.llm_not_configured")

    raw_findings: List[Finding] = []
    touched_test_files = any(
        p.rsplit("/", 1)[-1].startswith("test_") or p.endswith("_test.py") for p in files_reviewed
    )

    def _existing_tests_reference(func_name: str) -> bool:
        if reader is None:
            return False
        try:
            return len(reader.search_repository(func_name, max_results=1)) > 0
        except Exception:
            return False

    semgrep_targets: List[str] = []

    for path in files_reviewed:
        file_diff = file_diffs[path]
        file_content = reader.read_file(path) if reader else None
        raw_findings.extend(run_rule_based_checks(file_diff, file_content))
        raw_findings.extend(check_missing_tests(file_diff, touched_test_files, _existing_tests_reference))

        if llm_provider is not None:
            context = file_content or ""
            raw_findings.extend(_llm_findings_for_file(llm_provider, path, file_diff, context))

    reviewed_file_diffs = {path: file_diffs[path] for path in files_reviewed}
    raw_findings.extend(run_semgrep_for_diffs(reviewed_file_diffs, repo_reader=reader))

    findings = [f for f in raw_findings if f.confidence >= threshold]

    dropped = len(raw_findings) - len(findings)
    if dropped:
        logger.info(
            "review.filtered_low_confidence",
            extra={"dropped": dropped, "threshold": threshold},
        )

    summary = _build_summary(files_reviewed, findings)
    logger.info("review.completed", extra={"finding_count": len(findings)})

    return ReviewResult(
        status=ReviewStatus.COMPLETED,
        files_reviewed=files_reviewed,
        findings=findings,
        summary=summary,
    )
