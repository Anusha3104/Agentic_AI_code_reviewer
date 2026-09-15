"""
Repository context retrieval.

Provides the building blocks the agent (and the deterministic checks)
use to look beyond the changed lines themselves:

    read_file()             -- read one file's content
    find_related_files()    -- files that look related by name
    get_existing_tests()    -- test files that likely cover a given file
    search_repository()     -- text/regex search across the repo
    inspect_git_history()   -- recent commits touching a file

We deliberately never send the whole repository to the LLM -- every
method here returns a small, targeted slice of context (a handful of
files, a handful of matching lines, a handful of commits).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional


class RepositoryReader:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    def read_file(self, relative_path: str) -> Optional[str]:
        """Read a file's content relative to the repo root. Returns None if missing."""
        full_path = self.repo_path / relative_path
        try:
            full_path = full_path.resolve()
            # Prevent path traversal outside the repository root.
            full_path.relative_to(self.repo_path)
        except (ValueError, OSError):
            return None

        if not full_path.exists() or not full_path.is_file():
            return None

        try:
            return full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def find_related_files(self, relative_path: str) -> List[str]:
        """
        Very small heuristic: files in the same directory that share the
        same stem prefix (e.g. `auth.py` <-> `test_auth.py`).

        Full call-graph / import-based context retrieval is a Phase 4
        feature (see docs/ARCHITECTURE.md) and is intentionally not
        implemented here.
        """
        target = self.repo_path / relative_path
        directory = target.parent
        if not directory.exists():
            return []

        stem = target.stem
        related = []
        for entry in directory.iterdir():
            if entry.is_file() and entry != target and stem in entry.stem:
                related.append(str(entry.relative_to(self.repo_path)))
        return related

    def get_existing_tests(self, relative_path: str) -> List[str]:
        """
        Heuristic lookup for a test file that likely covers `relative_path`.
        Looks for `test_<name>.py` / `<name>_test.py` anywhere in the repo.
        """
        stem = Path(relative_path).stem
        candidates = {f"test_{stem}.py", f"{stem}_test.py"}
        matches = []
        for root, _dirs, files in os.walk(self.repo_path):
            for f in files:
                if f in candidates:
                    matches.append(
                        str((Path(root) / f).relative_to(self.repo_path))
                    )
        return matches

    def search_repository(self, query: str, max_results: int = 15, max_file_size_bytes: int = 300_000) -> List[str]:
        """
        Simple text search across the repository for a literal string or
        regex pattern. Returns up to `max_results` "path:line: snippet"
        matches. This intentionally skips binary files, VCS directories,
        and very large files so we never scan (or send to the LLM) the
        entire repository.
        """
        import re as _re

        SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
        try:
            pattern = _re.compile(query)
        except _re.error:
            pattern = _re.compile(_re.escape(query))

        matches: List[str] = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                if len(matches) >= max_results:
                    return matches
                fpath = Path(root) / fname
                try:
                    if fpath.stat().st_size > max_file_size_bytes:
                        continue
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if pattern.search(line):
                        rel = fpath.relative_to(self.repo_path)
                        snippet = line.strip()[:160]
                        matches.append(f"{rel}:{i}: {snippet}")
                        if len(matches) >= max_results:
                            break
        return matches

    def inspect_git_history(self, relative_path: str, max_commits: int = 5) -> List[str]:
        """
        Return up to `max_commits` short log lines ("<hash> <subject>")
        for a file's recent history, using `git log`. Returns [] if the
        path isn't a git repository or the file has no history -- this
        must never raise, since it's purely supplementary context.
        """
        import subprocess

        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"-{max_commits}",
                    "--follow",
                    "--pretty=format:%h %s",
                    "--",
                    relative_path,
                ],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]
