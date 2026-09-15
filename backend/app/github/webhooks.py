"""
GitHub webhook handling: signature verification and event parsing.

Per the project spec: "Verify webhook signatures. Do not trust arbitrary
webhook requests." Every incoming webhook MUST pass `verify_signature`
before its payload is trusted or processed.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Optional

RELEVANT_PR_ACTIONS = {"opened", "synchronize", "reopened"}


def verify_signature(payload_body: bytes, signature_header: Optional[str], secret: str) -> bool:
    """
    Verify the `X-Hub-Signature-256` header GitHub sends with every
    webhook delivery. Uses a constant-time comparison to avoid timing
    attacks. Returns False (never raises) for any malformed input.
    """
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(secret.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


@dataclass
class PullRequestEvent:
    action: str
    owner: str
    repo: str
    pr_number: int
    installation_id: Optional[str]
    is_relevant: bool


def parse_pull_request_event(payload: dict) -> Optional[PullRequestEvent]:
    """
    Parse a `pull_request` webhook payload. Returns None if the payload
    doesn't look like a pull_request event at all (missing required keys)
    so the caller can respond appropriately without crashing.
    """
    try:
        action = payload["action"]
        pr_number = payload["pull_request"]["number"]
        repo_full = payload["repository"]["full_name"]
        owner, repo = repo_full.split("/", 1)
        installation_id = str(payload["installation"]["id"]) if "installation" in payload else None
    except (KeyError, TypeError, ValueError):
        return None

    return PullRequestEvent(
        action=action,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        installation_id=installation_id,
        is_relevant=action in RELEVANT_PR_ACTIONS,
    )
