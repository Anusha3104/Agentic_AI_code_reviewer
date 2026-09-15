"""
Minimal unified-diff parser.

We deliberately avoid pulling in a heavy diff-parsing dependency for
Phase 1 so the CLI has almost no install footprint. This module understands
standard `git diff` / GitHub PR diff output:

    diff --git a/path/to/file.py b/path/to/file.py
    index 1234567..89abcde 100644
    --- a/path/to/file.py
    +++ b/path/to/file.py
    @@ -10,6 +10,7 @@ def foo():
    -old line
    +new line

It extracts, per changed file, the list of *added* lines together with
their line numbers in the new version of the file. Reviews only care
about lines the PR actually introduces or changes -- we never want to
flag pre-existing code the author didn't touch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List


HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
DIFF_GIT_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")


@dataclass
class AddedLine:
    line_number: int  # line number in the NEW file
    content: str


@dataclass
class FileDiff:
    path: str
    added_lines: List[AddedLine] = field(default_factory=list)
    removed_line_count: int = 0
    is_new_file: bool = False
    is_deleted_file: bool = False

    @property
    def added_line_numbers(self) -> List[int]:
        return [al.line_number for al in self.added_lines]


def parse_diff(diff_text: str) -> Dict[str, FileDiff]:
    """Parse a unified diff and return {file_path: FileDiff}."""
    files: Dict[str, FileDiff] = {}
    current: FileDiff | None = None
    new_line_no = 0

    for raw_line in diff_text.splitlines():
        git_match = DIFF_GIT_RE.match(raw_line)
        if git_match:
            path = git_match.group(2)
            current = files.get(path) or FileDiff(path=path)
            files[path] = current
            continue

        if current is None:
            continue

        if raw_line.startswith("new file mode"):
            current.is_new_file = True
            continue

        if raw_line.startswith("deleted file mode"):
            current.is_deleted_file = True
            continue

        hunk_match = HUNK_HEADER_RE.match(raw_line)
        if hunk_match:
            new_line_no = int(hunk_match.group(2))
            continue

        if raw_line.startswith("+++") or raw_line.startswith("---"):
            continue

        if raw_line.startswith("+"):
            current.added_lines.append(
                AddedLine(line_number=new_line_no, content=raw_line[1:])
            )
            new_line_no += 1
        elif raw_line.startswith("-"):
            current.removed_line_count += 1
            # removed lines don't consume a new-file line number
        else:
            # context line (or "\ No newline at end of file" etc.)
            new_line_no += 1

    return files


def read_diff_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()
