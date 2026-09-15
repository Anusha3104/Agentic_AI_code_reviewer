# Architecture

## Full target pipeline (end state, after Phase 11)

```
GitHub Pull Request
        │
        ▼
GitHub Webhook (signature-verified)
        │
        ▼
FastAPI Backend  ──► enqueues a Review Job (status: queued)
        │
        ▼
LangGraph Agent
        │
        ├─► Fetch PR metadata / diff (GitHub API)
        ├─► Analyze changed files
        ├─► Determine + retrieve repository context (only what's relevant)
        ├─► Run static analysis (Semgrep, deterministic checks)
        ├─► Run tests (sandboxed)
        ├─► Run security analysis
        ├─► LLM review (Gemini, via LLMProvider abstraction)
        ├─► Validate each candidate finding (second LLM pass)
        ├─► Assign severity + confidence
        ├─► Filter below MIN_CONFIDENCE / low-value findings
        └─► Generate final review text
        │
        ▼
Post review + inline comments to GitHub PR
        │
        ▼
Store PR / Review / Finding rows in the database
        │
        ▼
React dashboard reads from the database via the FastAPI /api/* endpoints
```

## Current implementation (all phases)

The full pipeline above is implemented end-to-end. Two entrypoints exist:

1. **`review.py` / `app.services.review_engine.run_review()`** — the
   lighter, direct pipeline (used by default in the CLI). Runs
   deterministic checks + Semgrep + missing-tests heuristic + optional
   LLM review, all in a single pass.
2. **`app.agents.graph.run_agent_review()`** — the LangGraph agent
   version of the same pipeline, additionally running the finding
   **validation** stage (Phase 6) and structured as an explicit state
   graph rather than a linear function. This is what the GitHub webhook
   handler uses (`app/api/webhooks.py`), and is reachable from the CLI
   via `--use-agent`.

Both produce the exact same `ReviewResult` contract
(`app/models/finding.py`), so callers (CLI, API, webhook) don't need to
know which one produced a given review.

```
diff file ──► diff_parser.parse_diff()
                     │
repo path ──► repo_reader.RepositoryReader (context: files, tests, git history, search)
                     │
                     ▼
        rule_based_checks + semgrep_runner + testing_checks
                     │
                     ▼ (if GEMINI_API_KEY set)
              llm/gemini_provider.generate_review()
                     │
                     ▼ (agent path only)
              services/validator.validate_findings()
                     │
                     ▼
        review_engine / agents.nodes.filter_and_summarize_node
          - filters findings below MIN_CONFIDENCE
          - builds a summary string
                     │
                     ▼
        models/finding.ReviewResult  (structured, typed, JSON-serializable)
                     │
              ┌──────┴──────┐
              ▼             ▼
        review.py CLI   api/webhooks.py → GitHub PR review + database
```

This slice is designed so producers of `Finding` objects (rule-based,
Semgrep, LLM) all feed the same filtering/reporting path — the contract
(`backend/app/models/finding.py`) doesn't change shape as more analyzers
are added.

## Key design decisions

- **Deterministic tools for deterministic problems.** Phase 1's checks
  are regex/pattern-based on purpose — they're cheap, free, and 100%
  reproducible for well-known bug patterns (SQL/command injection,
  hardcoded secrets, bare except, off-by-one indexing). The LLM (Phase 2)
  is reserved for the reasoning-heavy checks (logic bugs, missing
  authorization, repository-consistency judgment calls) that a regex
  fundamentally can't do.
- **Confidence and severity are separate axes.** A finding can be
  `severity=critical` but `confidence=0.4` — it should still be dropped
  by the `MIN_CONFIDENCE` filter until a validation stage (Phase 6) can
  corroborate it.
- **Never send the whole repo to the LLM.** `RepositoryReader` retrieves
  only the specific file(s) a check needs; full repository-wide search
  (Phase 4) will follow the same "retrieve only what's relevant"
  principle.
- **Fail gracefully.** A missing repository path, an unreadable file, or
  a diff with no recognizable hunks should never crash the CLI — see the
  `test_run_review_handles_missing_repo_path_gracefully` test.
