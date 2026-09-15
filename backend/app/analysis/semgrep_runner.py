"""
Semgrep integration.

Per the project spec, "use deterministic tools for deterministic
problems" -- Semgrep is the deterministic tool for pattern-based security
and correctness checks that are more precisely expressed as an AST
pattern than a regex.

We ship our own small offline rule pack (semgrep_rules/bundled_rules.yml)
rather than depending on `semgrep --config=auto`, which requires network
access to the Semgrep Registry. This keeps the reviewer fully functional
with zero network access and zero cost, per the "Free Development
Requirement" (spec section 31). If `semgrep` isn't installed at all, this
module degrades gracefully -- it logs once and returns no findings rather
than crashing the review.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

from app.models.finding import Category, Finding, Severity

logger = logging.getLogger("analysis.semgrep")

RULES_PATH = Path(__file__).resolve().parent / "semgrep_rules" / "bundled_rules.yml"
SEMGREP_TIMEOUT_SECONDS = 60

_SEVERITY_MAP = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}
_CONFIDENCE_MAP = {
    "HIGH": 0.85,
    "MEDIUM": 0.75,
    "LOW": 0.6,
}


def is_semgrep_available() -> bool:
    return shutil.which("semgrep") is not None


def run_semgrep(file_paths: List[str]) -> List[Finding]:
    """
    Run the bundled Semgrep rule pack against a list of absolute file
    paths (only changed files should be passed in -- we never scan the
    whole repository). Returns [] if semgrep isn't installed, times out,
    or the rule file is missing; never raises.
    """
    if not file_paths:
        return []

    if not is_semgrep_available():
        logger.info("semgrep.not_installed")
        return []

    if not RULES_PATH.exists():
        logger.warning("semgrep.rules_missing", extra={"path": str(RULES_PATH)})
        return []

    cmd = ["semgrep", "--config", str(RULES_PATH), "--json", "--quiet", *file_paths]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=SEMGREP_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        logger.warning("semgrep.timeout", extra={"files": len(file_paths)})
        return []
    except OSError as exc:
        logger.warning("semgrep.execution_failed", extra={"error": str(exc)})
        return []

    if not result.stdout:
        return []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("semgrep.malformed_output")
        return []

    findings: List[Finding] = []
    for item in data.get("results", []):
        try:
            extra = item.get("extra", {})
            metadata = extra.get("metadata", {})
            severity = _SEVERITY_MAP.get(extra.get("severity", "WARNING"), Severity.MEDIUM)
            confidence = _CONFIDENCE_MAP.get(metadata.get("confidence", "MEDIUM"), 0.75)
            category_str = metadata.get("category", "correctness")
            category = Category(category_str) if category_str in Category._value2member_map_ else Category.CORRECTNESS

            findings.append(
                Finding(
                    file=item["path"],
                    line=item["start"]["line"],
                    category=category,
                    severity=severity,
                    confidence=confidence,
                    title=item["check_id"].split(".")[-1].replace("-", " ").title(),
                    description=extra.get("message", "Semgrep flagged this pattern."),
                    impact=extra.get("message", ""),
                    suggestion="Review this pattern against Semgrep's rule guidance and refactor if applicable.",
                    source="semgrep",
                )
            )
        except (KeyError, ValueError) as exc:
            logger.warning("semgrep.malformed_result", extra={"error": str(exc)})
            continue

    return findings


def run_semgrep_for_diffs(file_diffs: Dict[str, object], repo_reader=None) -> List[Finding]:
    """
    Run Semgrep across a set of changed files, given their FileDiff
    objects and an optional RepositoryReader for reading existing file
    content from disk.

    Semgrep needs real file content on disk to scan. For files that
    already exist in the repository, we scan the real file directly. For
    brand-new files introduced by the diff (nothing checked out on disk
    -- e.g. a webhook review with no local clone, or a diff-only local
    review), we reconstruct an approximation by writing just the added
    lines to a temp file with the same extension/name; that's exactly
    the new file's content for a pure addition, and is good enough to
    catch patterns living in the new code itself. Results are always
    returned with the *logical* repo-relative path, not the temp path.
    """
    if not file_diffs:
        return []

    path_for_semgrep: Dict[str, str] = {}  # target_path_on_disk -> logical_path
    real_targets: List[str] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for logical_path, file_diff in file_diffs.items():
            real_path = None
            if repo_reader is not None:
                candidate = repo_reader.repo_path / logical_path
                if candidate.exists():
                    real_path = candidate

            if real_path is not None:
                path_for_semgrep[str(real_path)] = logical_path
                real_targets.append(str(real_path))
            else:
                # Reconstruct from added lines only, preserving the
                # original filename/extension so language detection works.
                added_text = "\n".join(al.content for al in file_diff.added_lines)
                if not added_text.strip():
                    continue
                tmp_target = Path(tmp_dir) / Path(logical_path).name
                try:
                    tmp_target.write_text(added_text, encoding="utf-8")
                except OSError:
                    continue
                path_for_semgrep[str(tmp_target)] = logical_path
                real_targets.append(str(tmp_target))

        findings = run_semgrep(real_targets)

    for f in findings:
        f.file = path_for_semgrep.get(f.file, f.file)
    return findings
