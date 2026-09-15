"""
Missing-test detection.

Per the spec: "Do NOT automatically complain that every code change
needs a test. Only report missing tests when the change introduces
meaningful behavior that should reasonably be covered."

This module implements a conservative heuristic: it only flags a new
top-level function/method that (a) is non-trivial (has a branch, loop,
or exception handling -- i.e. actual logic, not a one-line wrapper) and
(b) has no existing or newly-added test file that appears to reference
it by name anywhere in the diff or the repository.
"""
from __future__ import annotations

import ast
from typing import List, Optional

from app.models.finding import Category, Finding, Severity
from app.services.diff_parser import FileDiff

MIN_BODY_COMPLEXITY_KEYWORDS = ("if ", "for ", "while ", "try:", "except", "raise ")


def _is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py")


def _added_function_names(file_diff: FileDiff) -> List[str]:
    """Best-effort extraction of newly-defined function names from added lines."""
    names = []
    for added in file_diff.added_lines:
        stripped = added.content.strip()
        if stripped.startswith("def ") and "(" in stripped:
            name = stripped[len("def "):stripped.index("(")].strip()
            if name and not name.startswith("_") and not name.startswith("test_"):
                names.append(name)
    return names


def _looks_nontrivial(file_diff: FileDiff, function_name: str) -> bool:
    """A very rough check: does the added code near this function contain
    real branching/looping/error-handling logic, or is it a trivial
    one-liner (e.g. a pure getter/wrapper)?"""
    added_text = "\n".join(al.content for al in file_diff.added_lines)
    return any(kw in added_text for kw in MIN_BODY_COMPLEXITY_KEYWORDS)


def check_missing_tests(
    file_diff: FileDiff,
    test_file_touched_in_diff: bool,
    existing_tests_reference_function,
) -> List[Finding]:
    """
    Args:
        file_diff: the diff for a single non-test source file.
        test_file_touched_in_diff: True if this PR also modifies a test
            file (a strong signal the new behavior IS covered).
        existing_tests_reference_function: callable(function_name) -> bool,
            checking whether any existing test in the repo already
            references this function name (see repo_reader.search_repository).
    """
    if _is_test_file(file_diff.path):
        return []
    if test_file_touched_in_diff:
        return []

    findings: List[Finding] = []
    for func_name in _added_function_names(file_diff):
        if not _looks_nontrivial(file_diff, func_name):
            continue
        if existing_tests_reference_function(func_name):
            continue

        findings.append(
            Finding(
                file=file_diff.path,
                line=next(
                    (al.line_number for al in file_diff.added_lines if f"def {func_name}(" in al.content),
                    1,
                ),
                category=Category.TESTING,
                severity=Severity.LOW,
                confidence=0.65,
                title=f"New function `{func_name}` appears to be untested",
                description=(
                    f"`{func_name}` contains conditional/loop/error-handling "
                    "logic but no test file in this PR or the existing "
                    "repository appears to reference it."
                ),
                impact=(
                    "Untested branching logic is more likely to contain "
                    "regressions that go unnoticed until production."
                ),
                suggestion=(
                    f"Add a unit test covering `{func_name}`'s main paths, "
                    "including at least one edge case."
                ),
                source="rule_based",
            )
        )
    return findings
