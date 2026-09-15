"""
Thin GitHub REST API client covering exactly what the reviewer needs:
PR metadata, changed files, diffs, file contents, and posting a review
(with inline comments). Deliberately not a full GitHub SDK.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

logger = logging.getLogger("github.client")

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 20


class GitHubAPIError(Exception):
    pass


@dataclass
class ChangedFile:
    filename: str
    status: str          # "added" | "modified" | "removed" | "renamed"
    patch: Optional[str]  # unified diff patch for this file (may be None for binary/large files)


class GitHubClient:
    def __init__(self, token: str, session: Optional[requests.Session] = None):
        self.token = token
        self.session = session or requests.Session()

    def _headers(self, accept: str = "application/vnd.github+json") -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{GITHUB_API_BASE}{path}"
        headers = kwargs.pop("headers", None) or self._headers()
        try:
            resp = self.session.request(
                method, url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs
            )
        except requests.RequestException as exc:
            logger.error("github.request_failed", extra={"path": path, "error": str(exc)})
            raise GitHubAPIError(f"GitHub request failed: {exc}") from exc

        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            raise GitHubAPIError("GitHub API rate limit exceeded.")
        if resp.status_code >= 400:
            raise GitHubAPIError(f"GitHub API error {resp.status_code} for {path}: {resp.text[:300]}")
        return resp

    # --- PR metadata -----------------------------------------------------

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        resp = self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
        return resp.json()

    def get_changed_files(self, owner: str, repo: str, pr_number: int) -> List[ChangedFile]:
        files: List[ChangedFile] = []
        page = 1
        while True:
            resp = self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                params={"per_page": 100, "page": page},
            )
            batch = resp.json()
            if not batch:
                break
            for item in batch:
                files.append(
                    ChangedFile(
                        filename=item["filename"],
                        status=item["status"],
                        patch=item.get("patch"),
                    )
                )
            if len(batch) < 100:
                break
            page += 1
        return files

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Fetch the full unified diff for a PR (compatible with our diff_parser)."""
        resp = self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            headers=self._headers(accept="application/vnd.github.v3.diff"),
        )
        return resp.text

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> Optional[str]:
        import base64

        try:
            resp = self._request(
                "GET", f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref}
            )
        except GitHubAPIError:
            return None
        data = resp.json()
        if data.get("encoding") == "base64" and "content" in data:
            try:
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            except (ValueError, TypeError):
                return None
        return None

    # --- Posting the review -----------------------------------------------

    def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: Optional[List[dict]] = None,
    ) -> dict:
        """
        Post a PR review. `comments` is a list of
        {"path": str, "line": int, "body": str} for inline comments.
        `event` is one of APPROVE / REQUEST_CHANGES / COMMENT.
        """
        payload: dict = {"body": body, "event": event}
        if comments:
            payload["comments"] = comments
        resp = self._request("POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", json=payload)
        return resp.json()
