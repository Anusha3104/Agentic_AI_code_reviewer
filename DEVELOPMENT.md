# Development Guide

## Prerequisites

- Python 3.11+ (tested with 3.12)
- Node.js 18+ (only needed from Phase 9 onward, for the dashboard)
- Git

## Setting up

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

## Project conventions

- **No hard-coded prompts in Python.** LLM prompts live in `prompts/*.txt`
  (Phase 2+ reads them from disk rather than embedding strings in code).
- **All `Finding`s go through `backend/app/models/finding.py`.** Any new
  analyzer (rule-based, LLM-based, Semgrep-based) must produce `Finding`
  objects matching that schema so the rest of the pipeline stays
  analyzer-agnostic.
- **Confidence threshold is configurable, never hard-coded**
  (`MIN_CONFIDENCE` in `.env`, overridable via `--min-confidence` in the
  CLI).
- **Never log secrets or raw source code.** Use
  `backend/app/utils/logging_setup.py`'s structured logger and pass only
  metadata (file counts, finding counts, statuses) as `extra=`.

## Adding a new deterministic check (Phase 1 style)

1. Add a `check_*(file_diff: FileDiff) -> List[Finding]` function to
   `backend/app/analysis/rule_based_checks.py`.
2. Register it in `ALL_CHECKS`.
3. Add both a "detects the bad pattern" test and a "does NOT flag the
   equivalent safe pattern" test to
   `backend/tests/test_rule_based_checks.py` — false-positive avoidance
   is a first-class requirement of this project, not an afterthought.

## Running tests during development

```bash
cd backend
pytest -v                     # full suite
pytest tests/test_rule_based_checks.py -v   # just one file
pytest -k sql_injection -v    # just matching tests
```

## Working on the CLI

```bash
python review.py --repo ./test-repository --diff ./test.diff --verbose
```

`--verbose` enables structured INFO logs to stderr so you can see each
pipeline stage (`review.started`, `review.filtered_low_confidence`,
`review.completed`, etc.).

## Phase checklist (do this after every phase, per the project spec)

- [ ] `pytest -v` passes with no failures
- [ ] Manually run `review.py` (or the relevant new entrypoint) and
      confirm the output looks correct
- [ ] Update `README.md` "Known Limitations" / feature list
- [ ] Do not remove or break any test or feature from a prior phase
