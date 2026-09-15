# Agentic AI Code Reviewer

An AI agent that reviews GitHub Pull Requests like a careful senior
engineer — surfacing high-value correctness, security, testing, and
repository-consistency issues while deliberately avoiding style nitpicks
and low-confidence noise.

> **Status: all 11 phases implemented.** 98 backend tests passing,
> evaluation harness scoring precision 1.00 / recall 1.00 / F1 1.00 on
> its 19-case dataset (deterministic + Semgrep pipeline, no LLM key
> required). See "Known Limitations" for what still needs your own
> credentials/hardware to fully exercise (a live Gemini key, a real
> GitHub App, and a Docker daemon).

---

## 1. Features

- **Local CLI** (`review.py`) — review any repo + diff with zero external
  dependencies.
- **LLM reviewer** — pluggable provider abstraction; ships with a Gemini
  (free tier) implementation. Swappable via `LLM_PROVIDER` with zero code
  changes elsewhere.
- **LangGraph agent** — a real stateful graph (fetch diff → retrieve
  context → static analysis → LLM review → validate → filter/summarize),
  reachable via `--use-agent` on the CLI and used by the GitHub webhook.
- **Repository context retrieval** — read files, find related files,
  locate existing tests, full-text search the repo, inspect git history.
- **Static analysis** — deterministic regex/AST-based checks (SQL/command
  injection, hardcoded secrets, bare `except`, insecure deserialization,
  off-by-one indexing) *plus* Semgrep with a bundled offline rule pack
  (`eval`/`exec`, `subprocess(shell=True)`, Flask `debug=True`, asserts
  used for validation) — no network access required.
- **Missing-test detection** — conservative heuristic that only flags
  genuinely untested, non-trivial new logic.
- **Finding validation** — a second LLM pass that can discard
  low-value/incorrect candidate findings before they're shown.
- **GitHub integration** — GitHub App JWT auth, webhook signature
  verification, PR/diff fetching, posting a review with inline comments,
  duplicate-delivery protection.
- **Database** — SQLAlchemy models (Repository, PullRequest, Review,
  Finding) on SQLite (dev) or PostgreSQL (prod via Docker).
- **REST API** — FastAPI app exposing repositories/PRs/reviews/findings
  endpoints plus the webhook receiver.
- **React + Vite dashboard** — Dashboard, Pull Requests, Pull Request
  Detail, and Review Details pages.
- **Evaluation framework** — 19 hand-built test cases (11 "should flag"
  across every category, 8 "should NOT flag" legitimate code) with a
  precision/recall/F1 harness.
- **Docker** — Dockerfiles for backend/frontend + a `docker-compose.yml`
  wiring up PostgreSQL too.
- **98 automated tests** (`pytest`), all using mocked GitHub/LLM calls —
  no live credentials needed to run the suite.

---

## 2. Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full pipeline diagram.
In one line: **diff → parse → repo context → deterministic checks + Semgrep
+ LLM → validate → filter → structured review → GitHub → database →
dashboard**.

## 3. Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic |
| Agent | LangGraph |
| LLM | Gemini API (free tier), pluggable provider interface |
| Analysis | Deterministic rule-based checks + Semgrep (bundled offline rules) |
| Database | SQLite (dev, default) / PostgreSQL (prod, via Docker) |
| Frontend | React + Vite |
| Testing | pytest, mocked GitHub/LLM responses, FastAPI TestClient |

## 4. Installation

```bash
git clone <this-repo>
cd agentic-code-reviewer
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env
```

`pip install` also installs Semgrep (used by the bundled offline rule
pack) and FastAPI/SQLAlchemy for the backend server. If you only want the
Phase-1-style CLI with the lightest footprint, `pip install pydantic
python-dotenv requests` is enough — everything else degrades gracefully
when not installed (see "Known Limitations").

## 5. Environment Variables

See [`.env.example`](.env.example):

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=

GITHUB_APP_ID=
GITHUB_PRIVATE_KEY=
GITHUB_WEBHOOK_SECRET=

DATABASE_URL=sqlite:///./dev.db

MIN_CONFIDENCE=0.80
MAX_FILES_PER_REVIEW=20
MAX_TOKENS_PER_REVIEW=8000
TEST_TIMEOUT_SECONDS=120
```

Everything works with all of these blank except `MIN_CONFIDENCE` /
`MAX_FILES_PER_REVIEW` (which have sane defaults anyway) — the system is
designed to degrade gracefully with no LLM key and no GitHub App
configured, running only its deterministic + Semgrep checks.

## 6. Gemini API Setup

1. Get a free key at [Google AI Studio](https://aistudio.google.com/).
2. Put it in `.env` as `GEMINI_API_KEY=...`.
3. That's it — `app/llm/factory.py` picks it up automatically; no other
   config or code changes needed.

## 7. GitHub App Setup

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New
   GitHub App**.
2. Set the webhook URL to `https://<your-public-url>/webhooks/github`
   (use [ngrok](https://ngrok.com) or similar for local testing).
3. Generate a **webhook secret** and put it in `.env` as
   `GITHUB_WEBHOOK_SECRET`.
4. Under **Permissions**, grant: Pull requests (Read & write), Contents
   (Read-only), Metadata (Read-only).
5. Subscribe to the **Pull request** event.
6. Generate a **private key** (downloads a `.pem` file) — put its full
   contents in `.env` as `GITHUB_PRIVATE_KEY` (keep the `\n`s literal or
   use a `.env` tool that supports multi-line values).
7. Note the **App ID** — put it in `.env` as `GITHUB_APP_ID`.
8. Install the App on a test repository.

## 8. Local Development Mode (works with zero setup)

Run the reviewer against any local repository + diff file — no GitHub,
no LLM, no database, no network access needed:

```bash
python review.py --repo ./test-repository --diff ./test.diff
python review.py --repo ./test-repository --diff ./test.diff --use-agent   # full LangGraph pipeline
python review.py --repo <path> --diff <path> [--min-confidence 0.7] [--no-llm] [--json] [--verbose]
```

## 9. Running the Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Then check `http://localhost:8000/api/health` → `{"status": "ok"}`.
Tables are created automatically on startup (SQLite by default).

## 10. Running the Frontend

```bash
cd frontend
npm install
cp .env.example .env      # point VITE_API_BASE_URL at your backend
npm run dev
```

Open `http://localhost:5173`.

## 11. Running Tests

```bash
cd backend
pytest -v
```

98 tests covering the diff parser, rule-based checks, Semgrep
integration, repository context retrieval, the LLM provider (mocked
HTTP), the finding validator, the LangGraph agent, GitHub auth/client/
webhooks (mocked), the database layer, and the FastAPI app end-to-end.

## 12. Running Evaluation

```bash
python evaluation/evaluate.py                # deterministic + Semgrep, free, no API key
python evaluation/evaluate.py --use-llm       # also exercises Gemini (needs GEMINI_API_KEY)
python evaluation/evaluate.py --use-agent     # runs the full LangGraph agent pipeline
```

See [`EVALUATION.md`](EVALUATION.md) for the full methodology and current
scores (precision 1.00 / recall 1.00 / F1 1.00 on the bundled dataset).

## 13. Docker Setup

```bash
cp .env.example .env      # fill in what you have; blank Gemini/GitHub values are fine to start
docker compose up --build
```

This starts PostgreSQL, the FastAPI backend (`:8000`), and the frontend
(`:5173`, served by nginx). **Note:** the Dockerfiles/compose file were
written carefully against standard, well-tested patterns but could not
be build-tested in this development environment (no Docker daemon was
available) — please run `docker compose up --build` and let me know if
you hit anything, so it can be fixed.

## 14. Repository Structure

```
agentic-code-reviewer/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── config.py            # env-based settings
│   │   ├── api/                 # routes.py, webhooks.py, schemas.py, deps.py
│   │   ├── agents/               # state.py, nodes.py, graph.py (LangGraph)
│   │   ├── github/               # auth.py, client.py, webhooks.py
│   │   ├── llm/                  # base.py, gemini_provider.py, factory.py
│   │   ├── analysis/              # rule_based_checks.py, semgrep_runner.py,
│   │   │                            testing_checks.py, semgrep_rules/
│   │   ├── database/               # base.py, models.py, crud.py
│   │   ├── models/                  # finding.py — Pydantic schemas
│   │   ├── services/                 # diff_parser, repo_reader, review_engine, validator
│   │   └── utils/                     # logging_setup.py, prompt_loader.py
│   ├── tests/                          # pytest suite (98 tests)
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/                             # React + Vite dashboard
│   └── src/{pages,components}/
├── prompts/                                # reviewer/validator/summarizer prompt templates
├── evaluation/                              # generate_cases.py, evaluate.py, test_cases/, expected_findings/
├── docker/                                   # Dockerfile.backend, Dockerfile.frontend
├── test-repository/                           # sample repo used by the demo diff
├── test.diff                                   # sample diff used by the demo
├── review.py                                    # local CLI entrypoint
├── docker-compose.yml
├── .env.example
├── .gitignore / .dockerignore
└── README.md
```

## 15. Example PR / Example Review

`test-repository/src/user_service.py` contains a function with a SQL
injection vulnerability. `test.diff` modifies it to add a hardcoded API
token and a bare `except:`, and adds a new file with an off-by-one bug.

```bash
python review.py --repo ./test-repository --diff ./test.diff
```

Expected output (abbreviated):

```
Reviewed 2 changed file(s) and identified 4 high-confidence issue(s)
(1 critical, 2 high, 1 medium).

[1] CRITICAL / security (confidence: 0.8)
    File: src/user_service.py:4
    Title: Possible hardcoded secret
...
```

## 16. Known Limitations

- **No live LLM/GitHub testing was possible in this development
  environment** — this sandbox has no network access to
  `generativelanguage.googleapis.com`, and no real GitHub App
  credentials exist to test against. Every LLM and GitHub code path is
  covered by unit tests with mocked HTTP responses instead. Please test
  with your own `GEMINI_API_KEY` and GitHub App and let me know if
  anything needs adjusting.
- **Docker was not build-tested** for the same reason (no Docker daemon
  in this environment) — see section 13.
- **Evaluation dataset has 19 cases, not 50.** It covers every required
  category (correctness, security ×6 patterns, testing) in both
  directions (should-flag / should-not-flag) with hand-verified,
  non-redundant cases rather than padding the count with near-duplicates.
  `evaluation/generate_cases.py` makes it mechanical to add more — see
  `EVALUATION.md` for suggested next cases (authz bugs, race conditions,
  resource leaks, XSS, SSRF, repository-consistency violations).
- **Semgrep on brand-new files** (introduced by a diff, not yet checked
  out anywhere) is scanned via a reconstruction of just the added lines,
  not the true full file — accurate for pure-addition diffs, approximate
  otherwise (see `run_semgrep_for_diffs` in `semgrep_runner.py`).
- **No database migrations** — tables are created with
  `Base.metadata.create_all()` at startup (fine for SQLite dev and this
  project's scope); a production system would add Alembic.
- **The webhook handler doesn't check out the PR branch locally**, so
  repository-context retrieval (related files, existing tests, git
  history) is diff-only in that flow, not full-repo, unless you extend
  it with a real clone step.
- **No background task queue** — the webhook handler runs the review
  synchronously, which is fine for typical PR sizes but would benefit
  from a queue (Celery/RQ) under heavy load.

## 17. Future Improvements

- Grow the evaluation dataset toward 50+ cases (see above).
- Add a real local-checkout step to the webhook flow for full repository
  context on GitHub-triggered reviews.
- Add Alembic migrations.
- Add a background task queue for webhook processing.
- Add Groq / OpenRouter providers (the `LLMProvider` interface already
  supports this — see `app/llm/factory.py`'s commented extension points).
- Add authentication to the dashboard/API for multi-user deployments.

---

## Development Strategy — all phases complete

| Phase | Status | Adds |
|---|---|---|
| 1 | ✅ | Local CLI, deterministic checks |
| 2 | ✅ | Gemini API integration via pluggable `LLMProvider` |
| 3 | ✅ | LangGraph agent workflow |
| 4 | ✅ | Repository context retrieval |
| 5 | ✅ | Static analysis (Semgrep, bundled offline rules) |
| 6 | ✅ | Finding validation agent |
| 7 | ✅ | GitHub App, webhooks, PR review posting |
| 8 | ✅ | SQLite/PostgreSQL database and models |
| 9 | ✅ | React + Vite dashboard |
| 10 | ✅ | Evaluation framework (19-case dataset, P/R/F1) |
| 11 | ✅ | Docker + deployment (untested — see Known Limitations) |

## Security

- API keys and tokens are always loaded from environment variables —
  never hard-coded, never committed (`.env` is gitignored).
- Webhook payloads are rejected unless their HMAC-SHA256 signature
  verifies against `GITHUB_WEBHOOK_SECRET` (constant-time comparison).
- Logging is structured and never includes secrets or unnecessary raw
  source code (see `backend/app/utils/logging_setup.py`).
- `RepositoryReader.read_file()` blocks path traversal outside the repo
  root.
- CORS on the FastAPI app is restricted to the local dev frontend origin
  by default — tighten before any real deployment.
- No repository code is ever executed on the host (no PR-code test
  execution is implemented in this MVP — see Known Limitations).

## License

MIT (adjust as needed for your use case).
