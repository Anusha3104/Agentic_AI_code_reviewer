#!/usr/bin/env python3
"""
Local Development Mode CLI (Phase 1).

Lets you run the reviewer against a repository + diff without any GitHub
or LLM integration, so the core pipeline can be built and tested for free
before wiring up external services.

Usage:
    python review.py --repo ./test-repository --diff ./test.diff
    python review.py --repo ./test-repository --diff ./test.diff --min-confidence 0.7
    python review.py --repo ./test-repository --diff ./test.diff --json
"""
import argparse
import json
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.diff_parser import read_diff_file  # noqa: E402
from app.services.review_engine import run_review  # noqa: E402
from app.utils.logging_setup import configure_logging  # noqa: E402
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Agentic AI Code Reviewer locally against a repo + diff."
    )
    parser.add_argument("--repo", required=True, help="Path to the repository the diff applies to")
    parser.add_argument("--diff", required=True, help="Path to a unified diff file (git diff output)")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help="Override MIN_CONFIDENCE threshold (default: from .env / config, currently 0.80)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the raw JSON review result instead of the human-readable report",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable the LLM reviewer even if GEMINI_API_KEY is set (deterministic checks only)",
    )
    parser.add_argument(
        "--use-agent",
        action="store_true",
        help="Run the full LangGraph agent pipeline (context retrieval, Semgrep, validation) "
        "instead of the lighter review_engine pipeline",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging to stderr",
    )
    return parser.parse_args()


def render_human_report(result_dict: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("AGENTIC AI CODE REVIEWER — Local Review Report")
    lines.append("=" * 70)
    lines.append(f"Status: {result_dict['status']}")
    lines.append(f"Files reviewed: {len(result_dict['files_reviewed'])}")
    for f in result_dict["files_reviewed"]:
        lines.append(f"  - {f}")
    lines.append("")
    lines.append(result_dict["summary"])
    lines.append("")

    findings = sorted(
        result_dict["findings"],
        key=lambda f: SEVERITY_ORDER.get(f["severity"], 99),
    )

    if not findings:
        lines.append("No findings to display.")
    else:
        for i, f in enumerate(findings, 1):
            lines.append("-" * 70)
            lines.append(
                f"[{i}] {f['severity'].upper()} / {f['category']} "
                f"(confidence: {f['confidence']})"
            )
            lines.append(f"    File: {f['file']}:{f['line']}")
            lines.append(f"    Title: {f['title']}")
            lines.append(f"    Description: {f['description']}")
            lines.append(f"    Impact: {f['impact']}")
            lines.append(f"    Suggestion: {f['suggestion']}")
    lines.append("=" * 70)
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    configure_logging(level=logging.INFO if args.verbose else logging.WARNING)

    try:
        diff_text = read_diff_file(args.diff)
    except OSError as exc:
        print(f"Error: could not read diff file '{args.diff}': {exc}", file=sys.stderr)
        return 1

    if not Path(args.repo).exists():
        print(
            f"Warning: repo path '{args.repo}' does not exist. "
            "Continuing with diff-only analysis (no surrounding file context).",
            file=sys.stderr,
        )

    if args.use_agent:
        from app.agents.graph import run_agent_review

        result = run_agent_review(
            repo_path=args.repo,
            diff_text=diff_text,
            min_confidence=args.min_confidence,
            use_llm=not args.no_llm,
        )
    else:
        result = run_review(
            repo_path=args.repo,
            diff_text=diff_text,
            min_confidence=args.min_confidence,
            use_llm=not args.no_llm,
        )
    result_dict = result.to_public_dict()

    if args.json:
        print(json.dumps(result_dict, indent=2))
    else:
        print(render_human_report(result_dict))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
