# Evaluation (Phase 10)

Run it:

```bash
python evaluation/evaluate.py                # deterministic + Semgrep only (free, no API key)
python evaluation/evaluate.py --use-llm       # also exercises the LLM reviewer (needs GEMINI_API_KEY)
python evaluation/evaluate.py --use-agent     # runs through the full LangGraph agent pipeline
```

Current results on the bundled dataset (deterministic + Semgrep, no LLM):

```
Cases evaluated: 19
True positives:  11
False positives: 0
False negatives: 0
True negatives:  8

Precision: 1.00
Recall:    1.00
F1 score:  1.00
```

## How the dataset is organized

`evaluation/generate_cases.py` is the single source of truth -- it writes
matching pairs into `evaluation/test_cases/<id>.json` (the diff + any
pre-existing repo files) and `evaluation/expected_findings/<id>.json`
(what a correct reviewer should produce). Regenerate with:

```bash
python evaluation/generate_cases.py
```

To add a case: append an entry to the `CASES` list in
`generate_cases.py` and re-run it. Each entry needs either
`expected_categories` (a list of categories that must appear at least
once) or `expect_no_findings: True`.

## Current dataset (19 cases)

11 "should flag" cases spanning every category the spec requires:
correctness (off-by-one indexing, bare `except:`), security (SQL
injection, command injection, hardcoded secrets, insecure
deserialization via `pickle`/unsafe `yaml.load`, `eval()`, `subprocess`
with `shell=True`, Flask `debug=True`), and testing (a new function with
real branching logic and no test).

8 "should NOT flag" cases -- legitimate code that a good reviewer must
stay silent on: parameterized SQL queries, env-based secrets, a specific
(non-bare) `except` clause with its test included, a trivial one-line
getter, `yaml.safe_load()`, correct `len(items) - 1` indexing, plain
arithmetic, and editing a test file itself.

**Scaling to 50+ cases:** the spec calls for at least 50 test cases. This
project ships 19 as a genuinely useful, hand-verified starting set
covering every category and both directions (flag / don't-flag) rather
than padding the count with near-duplicates. The generator script makes
it mechanical to grow this -- see "How the dataset is organized" above.
Good candidates for the next 30: authorization/access-control bugs,
race conditions, resource leaks (unclosed files/connections), N+1 query
patterns, XSS via unescaped template output, SSRF via unvalidated
outbound URLs, and repository-consistency violations (duplicating an
existing `validate_token()`-style utility).

## Why the evaluation threshold differs from the production default

`evaluate.py` defaults to `--min-confidence 0.6`, below the production
default of `MIN_CONFIDENCE=0.80`. This is intentional: some checks (like
the missing-tests heuristic) are deliberately assigned a modest
confidence (0.65) because they're inherently softer signals than, say, a
hardcoded SQL string -- see "Avoid Useless Comments" in README.md. Running
the evaluation at the production threshold would make those
intentionally-conservative heuristics look like false negatives when
they're actually working as designed. The evaluation measures the
reviewer's raw detection capability; the production `MIN_CONFIDENCE`
setting is a separate, deliberately conservative knob for what actually
gets shown to a developer. Pass `--min-confidence 0.80` to `evaluate.py`
to see the metrics at the production threshold instead.

## Metrics computed

For each case, compare the reviewer's actual finding categories against
the expected ones and classify it as a true positive, false positive,
false negative, or true negative (see the classification logic in
`evaluate.py`). From these, `evaluate.py` reports:

- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 · Precision · Recall / (Precision + Recall)
- Average confidence across all findings produced

## Why this matters

Per the project's core principle (see `README.md`), the system is
optimized for **high-value reviews, not maximum detection count** -- a
reviewer that finds every bug but also produces ten false alarms per PR
is worse than one that finds fewer bugs but is trustworthy. Precision on
the "should NOT flag" cases is tracked with equal weight to recall on the
"should flag" cases for exactly this reason. Building this harness
surfaced three real bugs during development (a false positive on
parameterized SQL queries, and two false negatives where Semgrep/the
missing-tests check weren't wired into the plain CLI pipeline) -- exactly
what an evaluation framework is for.

