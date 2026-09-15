"""
Deterministic, high-confidence checks.

Phase 1 does not have an LLM wired up yet (that's Phase 2), so to prove
the end-to-end pipeline -- diff -> analysis -> structured findings -> review
-- we start with a small set of deterministic, regex/AST-based checks for
patterns that are almost always worth a human's attention.

This module intentionally implements only a handful of *high-value*
checks rather than trying to be a general linter. Per the project spec,
formatting/style issues are explicitly out of scope everywhere in this
system, including here.

From Phase 2 onward, an LLM-based analyzer will run *alongside* these
deterministic checks (not instead of them) -- "use deterministic tools
for deterministic problems and the LLM for reasoning/contextual analysis."
"""
from __future__ import annotations

import ast
import re
from typing import List

from app.models.finding import Category, Finding, Severity
from app.services.diff_parser import FileDiff

PYTHON_EXTENSIONS = (".py",)


def _is_python_file(path: str) -> bool:
    return path.endswith(PYTHON_EXTENSIONS)


def check_sql_injection(file_diff: FileDiff) -> List[Finding]:
    """Flag SQL strings built via concatenation or unsafe interpolation.

    Deliberately does NOT flag parameterized queries that pass a `%s` /
    `?` placeholder as a literal inside the SQL string and bind values
    separately (e.g. `db.execute(query, (user_id,))`) -- that's the safe
    pattern, and penalizing it would be exactly the kind of false
    positive this project is built to avoid.
    """
    findings: List[Finding] = []
    sql_keyword_re = re.compile(
        r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.IGNORECASE
    )
    # String concatenation: a quoted string immediately followed by `+`.
    concatenation_re = re.compile(r"""["']\s*\+|\+\s*["']""")
    # Real % string-formatting applied to the SQL string itself: the
    # `%` operator appears AFTER the closing quote (e.g. `"..." % (x,)`),
    # as opposed to a `%s`/`%d` placeholder living safely INSIDE the
    # quoted string for parameterized execution.
    percent_format_re = re.compile(r"""["']\s*%\s*[\(\w]""")
    f_string_re = re.compile(r"""f["']""")

    for added in file_diff.added_lines:
        line = added.content
        if not sql_keyword_re.search(line):
            continue

        looks_unsafe = (
            concatenation_re.search(line)
            or percent_format_re.search(line)
            or f_string_re.search(line)
            or ".format(" in line
        )

        if looks_unsafe:
            findings.append(
                Finding(
                    file=file_diff.path,
                    line=added.line_number,
                    category=Category.SECURITY,
                    severity=Severity.HIGH,
                    confidence=0.9,
                    title="Possible SQL injection via string concatenation",
                    description=(
                        "This line builds a SQL query by concatenating or "
                        "interpolating a variable directly into the query "
                        "string instead of using parameterized queries."
                    ),
                    impact=(
                        "An attacker who controls the interpolated value may "
                        "be able to alter the query's meaning, read, modify, "
                        "or delete data the application should not expose."
                    ),
                    suggestion=(
                        "Use parameterized queries / prepared statements "
                        "(e.g. cursor.execute(query, (param,))) instead of "
                        "building SQL with string concatenation or formatting."
                    ),
                )
            )
    return findings


def check_command_injection(file_diff: FileDiff) -> List[Finding]:
    """Flag shell execution built from concatenated/formatted strings."""
    findings: List[Finding] = []
    shell_call_re = re.compile(
        r"\b(os\.system|os\.popen|subprocess\.(call|run|Popen|check_output))\s*\("
    )
    for added in file_diff.added_lines:
        line = added.content
        if not shell_call_re.search(line):
            continue
        if "+" in line or "%" in line or ".format(" in line or "shell=True" in line:
            findings.append(
                Finding(
                    file=file_diff.path,
                    line=added.line_number,
                    category=Category.SECURITY,
                    severity=Severity.HIGH,
                    confidence=0.85,
                    title="Possible command injection",
                    description=(
                        "A shell command is built using string concatenation "
                        "or formatting (or invoked with shell=True) using "
                        "values that may come from user input."
                    ),
                    impact=(
                        "An attacker who influences the interpolated value "
                        "could execute arbitrary commands on the host."
                    ),
                    suggestion=(
                        "Avoid shell=True and string-built commands. Pass "
                        "arguments as a list to subprocess.run()/Popen() "
                        "and avoid the shell entirely where possible."
                    ),
                )
            )
    return findings


def check_hardcoded_secrets(file_diff: FileDiff) -> List[Finding]:
    """Flag what look like hardcoded API keys / passwords / tokens."""
    findings: List[Finding] = []
    # Matches: SOME_IDENTIFIER = "literal string of at least 8 non-space chars"
    assignment_re = re.compile(
        r"""^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["']([^"'\s]{8,})["']\s*$"""
    )
    secret_keywords = ("key", "secret", "password", "token", "passwd", "pwd")
    placeholder_re = re.compile(
        r"(?i)(your[_-]?key|xxxx|changeme|example|<.*>|os\.environ|getenv)"
    )

    for added in file_diff.added_lines:
        line = added.content
        match = assignment_re.match(line)
        if not match:
            continue
        identifier = match.group(1).lower()
        has_secret_keyword = any(kw in identifier for kw in secret_keywords)
        if has_secret_keyword and not placeholder_re.search(line):
            findings.append(
                Finding(
                    file=file_diff.path,
                    line=added.line_number,
                    category=Category.SECURITY,
                    severity=Severity.CRITICAL,
                    confidence=0.8,
                    title="Possible hardcoded secret",
                    description=(
                        "This line appears to assign a literal string to a "
                        "variable named like a secret/API key/password/token."
                    ),
                    impact=(
                        "Hardcoded secrets committed to source control can "
                        "be extracted by anyone with repository access and "
                        "may be leaked publicly."
                    ),
                    suggestion=(
                        "Load secrets from environment variables or a "
                        "secrets manager instead of hardcoding them, and "
                        "rotate this credential if it is real."
                    ),
                )
            )
    return findings


def check_bare_except(file_diff: FileDiff) -> List[Finding]:
    """Flag bare `except:` clauses that silently swallow all errors."""
    findings: List[Finding] = []
    for added in file_diff.added_lines:
        stripped = added.content.strip()
        if stripped == "except:" or re.match(r"^except\s*:\s*$", stripped):
            findings.append(
                Finding(
                    file=file_diff.path,
                    line=added.line_number,
                    category=Category.CORRECTNESS,
                    severity=Severity.MEDIUM,
                    confidence=0.82,
                    title="Bare except clause swallows all exceptions",
                    description=(
                        "A bare `except:` catches every exception, including "
                        "KeyboardInterrupt and SystemExit, and can hide bugs "
                        "by silently swallowing unrelated errors."
                    ),
                    impact=(
                        "Real bugs or failures may pass unnoticed, making "
                        "the system harder to debug and potentially leaving "
                        "it in an inconsistent state."
                    ),
                    suggestion=(
                        "Catch a specific exception type (e.g. `except "
                        "ValueError:`), or `except Exception:` if broad "
                        "handling is truly required, and log the error."
                    ),
                )
            )
    return findings


def check_insecure_deserialization(file_diff: FileDiff) -> List[Finding]:
    """Flag pickle.loads / unsafe yaml.load on potentially untrusted data."""
    findings: List[Finding] = []
    for added in file_diff.added_lines:
        line = added.content
        if re.search(r"\bpickle\.(loads?|Unpickler)\b", line):
            findings.append(
                Finding(
                    file=file_diff.path,
                    line=added.line_number,
                    category=Category.SECURITY,
                    severity=Severity.HIGH,
                    confidence=0.85,
                    title="Insecure deserialization with pickle",
                    description=(
                        "`pickle` deserializes arbitrary Python objects and "
                        "can execute arbitrary code if the data comes from "
                        "an untrusted source."
                    ),
                    impact=(
                        "If the pickled data is attacker-controlled, "
                        "deserializing it can lead to remote code execution."
                    ),
                    suggestion=(
                        "Avoid pickle for untrusted data. Use a safe format "
                        "like JSON, or verify/sign the data before "
                        "deserializing it."
                    ),
                )
            )
        elif re.search(r"\byaml\.load\s*\(", line) and "Loader=" not in line:
            findings.append(
                Finding(
                    file=file_diff.path,
                    line=added.line_number,
                    category=Category.SECURITY,
                    severity=Severity.MEDIUM,
                    confidence=0.8,
                    title="yaml.load() without a safe loader",
                    description=(
                        "yaml.load() without an explicit safe Loader can "
                        "construct arbitrary Python objects from the input."
                    ),
                    impact=(
                        "Parsing untrusted YAML this way can lead to "
                        "arbitrary code execution."
                    ),
                    suggestion=(
                        "Use yaml.safe_load() instead, or pass "
                        "Loader=yaml.SafeLoader explicitly."
                    ),
                )
            )
    return findings


def check_index_out_of_range(file_diff: FileDiff, file_content: str | None) -> List[Finding]:
    """
    Flag list/array indexing with `len(x)` used as an index without an
    off-by-one guard, e.g. `items[len(items)]`. This is a narrow,
    high-confidence pattern rather than a general bounds-checker.
    """
    findings: List[Finding] = []
    pattern = re.compile(r"(\w+)\s*\[\s*len\(\s*\1\s*\)\s*\]")
    for added in file_diff.added_lines:
        if pattern.search(added.content):
            findings.append(
                Finding(
                    file=file_diff.path,
                    line=added.line_number,
                    category=Category.CORRECTNESS,
                    severity=Severity.HIGH,
                    confidence=0.88,
                    title="Off-by-one index error",
                    description=(
                        "The code indexes a collection using `len(collection)` "
                        "as the index, which is always one past the last "
                        "valid index."
                    ),
                    impact=(
                        "This will raise an IndexError (or equivalent) at "
                        "runtime whenever this line executes."
                    ),
                    suggestion=(
                        "Use `len(collection) - 1` to reference the last "
                        "element, or reconsider the loop/index logic."
                    ),
                )
            )
    return findings


ALL_CHECKS = [
    check_sql_injection,
    check_command_injection,
    check_hardcoded_secrets,
    check_bare_except,
    check_insecure_deserialization,
]


def run_rule_based_checks(file_diff: FileDiff, file_content: str | None = None) -> List[Finding]:
    """Run all deterministic checks against a single file's diff."""
    if not _is_python_file(file_diff.path):
        return []

    findings: List[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(file_diff))
    findings.extend(check_index_out_of_range(file_diff, file_content))
    return findings
