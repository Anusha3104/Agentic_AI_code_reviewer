#!/usr/bin/env python3
"""
Evaluation harness (Phase 10).

Runs the reviewer against every case in test_cases/, compares the
resulting findings against expected_findings/, and reports precision,
recall, F1, and average confidence.

Usage:
    python evaluation/evaluate.py
    python evaluation/evaluate.py --use-llm     # also exercise the LLM reviewer (needs GEMINI_API_KEY)
    python evaluation/evaluate.py --use-agent   # run through the full LangGraph agent instead of review_engine

By default this runs with --no-llm semantics (deterministic checks +
Semgrep only) so the evaluation is free, reproducible, and doesn't
require any API key -- consistent with the project's "Free Development
Requirement". Pass --use-llm to also evaluate the LLM-augmented pipeline.

A case counts as a TRUE POSITIVE if it expects findings and the reviewer
produced at least one finding in each expected category. A case counts
as a FALSE POSITIVE if it expected zero findings but the reviewer
produced at least one. A case counts as a FALSE NEGATIVE if it expected
findings in a category the reviewer did not produce.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.review_engine import run_review  # noqa: E402

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "test_cases"
EXPECTED_DIR = HERE / "expected_findings"


@dataclass
class CaseResult:
    case_id: str
    expected_no_findings: bool
    expected_categories: list
    actual_categories: list
    confidences: list = field(default_factory=list)

    @property
    def is_true_positive(self) -> bool:
        if self.expected_no_findings:
            return False
        return all(cat in self.actual_categories for cat in self.expected_categories)

    @property
    def is_false_positive(self) -> bool:
        if self.expected_no_findings:
            return len(self.actual_categories) > 0
        # Expected findings but got completely unrelated/no categories.
        return len(self.expected_categories) > 0 and not self.is_true_positive and len(self.actual_categories) > 0

    @property
    def is_false_negative(self) -> bool:
        if self.expected_no_findings:
            return False
        return not all(cat in self.actual_categories for cat in self.expected_categories)

    @property
    def is_true_negative(self) -> bool:
        return self.expected_no_findings and len(self.actual_categories) == 0


def _materialize_repo(repo_files: dict, tmp_dir: Path) -> None:
    for rel_path, content in repo_files.items():
        full = tmp_dir / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)


def run_case(case: dict, expected: dict, use_llm: bool, use_agent: bool, min_confidence: float) -> CaseResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _materialize_repo(case.get("repo_files", {}), tmp_path)

        if use_agent:
            from app.agents.graph import run_agent_review

            result = run_agent_review(
                repo_path=str(tmp_path), diff_text=case["diff"], use_llm=use_llm, min_confidence=min_confidence
            )
        else:
            result = run_review(
                repo_path=str(tmp_path), diff_text=case["diff"], use_llm=use_llm, min_confidence=min_confidence
            )

        actual_categories = [f.category.value for f in result.findings]
        confidences = [f.confidence for f in result.findings]

    return CaseResult(
        case_id=case["id"],
        expected_no_findings=expected["expect_no_findings"],
        expected_categories=expected["expected_categories"],
        actual_categories=actual_categories,
        confidences=confidences,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the reviewer against the test case dataset.")
    parser.add_argument("--use-llm", action="store_true", help="Also exercise the LLM reviewer (needs GEMINI_API_KEY)")
    parser.add_argument("--use-agent", action="store_true", help="Run through the full LangGraph agent")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Confidence threshold used for THIS evaluation run (default 0.6, lower than the "
        "production default of 0.80). This measures the reviewer's raw detection capability "
        "separately from the reporting threshold -- MIN_CONFIDENCE in production is deliberately "
        "conservative (see README 'Avoid Useless Comments'), which would otherwise make some "
        "intentionally low-confidence heuristics (e.g. the missing-tests check) look like false "
        "negatives here when they're actually working as designed.",
    )
    args = parser.parse_args()

    case_files = sorted(CASES_DIR.glob("*.json"))
    if not case_files:
        print(f"No test cases found in {CASES_DIR}. Run generate_cases.py first.", file=sys.stderr)
        return 1

    results = []
    for case_file in case_files:
        case = json.loads(case_file.read_text())
        expected_file = EXPECTED_DIR / case_file.name
        if not expected_file.exists():
            print(f"Skipping {case['id']}: no matching expected_findings file.", file=sys.stderr)
            continue
        expected = json.loads(expected_file.read_text())
        results.append(run_case(case, expected, use_llm=args.use_llm, use_agent=args.use_agent, min_confidence=args.min_confidence))

    tp = sum(1 for r in results if r.is_true_positive)
    fp = sum(1 for r in results if r.is_false_positive)
    fn = sum(1 for r in results if r.is_false_negative)
    tn = sum(1 for r in results if r.is_true_negative)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    all_confidences = [c for r in results for c in r.confidences]
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    print("=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)
    print(f"Cases evaluated: {len(results)}")
    print(f"True positives:  {tp}")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")
    print(f"True negatives:  {tn}")
    print()
    print(f"Precision: {precision:.2f}")
    print(f"Recall:    {recall:.2f}")
    print(f"F1 score:  {f1:.2f}")
    print(f"Average confidence across all findings: {avg_confidence:.2f}")
    print("=" * 70)

    failures = [r for r in results if not (r.is_true_positive or r.is_true_negative)]
    if failures:
        print("\nCases that did not match expectations:")
        for r in failures:
            print(
                f"  - {r.case_id}: expected_categories={r.expected_categories} "
                f"expect_no_findings={r.expected_no_findings} "
                f"actual_categories={r.actual_categories}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
