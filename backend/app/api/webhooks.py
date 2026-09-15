"""
POST /webhooks/github

Receives GitHub `pull_request` events, verifies the signature, fetches
the PR diff, runs the agent, posts the review back to GitHub, and stores
the result -- the full pipeline described in ARCHITECTURE.md.

This is intentionally synchronous (no task queue) for the MVP: a review
typically takes a few seconds, well within GitHub's webhook timeout, and
a queue is easy to add later (see README.md "Future Improvements")
without changing this handler's shape.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents.graph import run_agent_review
from app.api.deps import get_db
from app.config import settings
from app.database import crud
from app.github.auth import GitHubAuthError, get_installation_token
from app.github.client import GitHubAPIError, GitHubClient
from app.github.webhooks import parse_pull_request_event, verify_signature

logger = logging.getLogger("api.webhooks")

router = APIRouter()

SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}


def _build_review_body(summary: str, findings: list) -> str:
    lines = [f"## 🤖 Agentic AI Code Reviewer\n", summary, ""]
    for f in findings:
        emoji = SEVERITY_EMOJI.get(f.severity.value, "")
        lines.append(f"### {emoji} {f.severity.value.upper()} — {f.title}")
        lines.append(f"**File:** `{f.file}:{f.line}` | **Category:** {f.category.value} | "
                     f"**Confidence:** {f.confidence:.0%}")
        lines.append(f"\n{f.description}\n")
        lines.append(f"**Impact:** {f.impact}\n")
        lines.append(f"**Suggested fix:** {f.suggestion}\n")
    return "\n".join(lines)


def _build_inline_comments(findings: list) -> list[dict]:
    seen = set()
    comments = []
    for f in findings:
        key = (f.file, f.line, f.title)
        if key in seen:
            continue  # never post duplicate comments
        seen.add(key)
        comments.append({
            "path": f.file,
            "line": f.line,
            "body": f"**{f.severity.value.upper()} / {f.category.value}** (confidence {f.confidence:.0%})\n\n"
                    f"{f.description}\n\n**Suggestion:** {f.suggestion}",
        })
    return comments


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
):
    raw_body = await request.body()

    if not verify_signature(raw_body, x_hub_signature_256, settings.github_webhook_secret):
        logger.warning("webhook.invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"unhandled event type: {x_github_event}"}

    payload = await request.json()
    event = parse_pull_request_event(payload)
    if event is None:
        raise HTTPException(status_code=400, detail="Malformed pull_request payload")

    if not event.is_relevant:
        return {"status": "ignored", "reason": f"action '{event.action}' is not reviewed"}

    repo = crud.get_or_create_repository(
        db, github_repo_id=f"{event.owner}/{event.repo}", name=event.repo, owner=event.owner
    )
    pr_payload = payload["pull_request"]
    pull_request = crud.get_or_create_pull_request(
        db,
        repository=repo,
        github_pr_number=event.pr_number,
        title=pr_payload.get("title", ""),
        author=pr_payload.get("user", {}).get("login", "unknown"),
        status=pr_payload.get("state", "open"),
    )

    if crud.has_running_or_queued_review(db, pull_request):
        logger.info("webhook.duplicate_skipped", extra={"pr": event.pr_number})
        return {"status": "skipped", "reason": "a review is already queued or running for this PR"}

    review = crud.create_review(db, pull_request, status="running")
    db.flush()

    try:
        if not event.installation_id:
            raise GitHubAuthError("Webhook payload had no installation id (is the GitHub App installed?)")

        token = get_installation_token(
            settings.github_app_id, settings.github_private_key, event.installation_id
        )
        client = GitHubClient(token=token.token)

        diff_text = client.get_pr_diff(event.owner, event.repo, event.pr_number)

        # Best-effort local checkout isn't available in the webhook context,
        # so repository context retrieval falls back gracefully to
        # diff-only analysis unless a local clone path is configured.
        result = run_agent_review(repo_path="/nonexistent-webhook-context", diff_text=diff_text)

        review_body = _build_review_body(result.summary, result.findings)
        inline_comments = _build_inline_comments(result.findings)
        client.post_review(
            event.owner, event.repo, event.pr_number,
            body=review_body, event="COMMENT", comments=inline_comments,
        )

        crud.save_review_result(db, review, result)
        logger.info("webhook.review_completed", extra={"pr": event.pr_number, "findings": len(result.findings)})
        return {"status": "completed", "review_id": review.id, "finding_count": len(result.findings)}

    except (GitHubAuthError, GitHubAPIError) as exc:
        logger.error("webhook.github_error", extra={"pr": event.pr_number, "error": str(exc)})
        crud.mark_review_failed(db, review, str(exc))
        raise HTTPException(status_code=502, detail=f"GitHub error: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive catch-all
        logger.error("webhook.unexpected_error", extra={"pr": event.pr_number, "error": str(exc)})
        crud.mark_review_failed(db, review, str(exc))
        raise HTTPException(status_code=500, detail="Internal error while processing review") from exc
