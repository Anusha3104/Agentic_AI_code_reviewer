"""
GitHub App authentication.

A GitHub App authenticates in two steps:
  1. Sign a short-lived JWT with the App's private key (proves "I am App
     <id>").
  2. Exchange that JWT for an installation access token scoped to one
     specific installation (repository/org), which is what's actually
     used to call the REST API.

Docs: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import jwt
import requests

GITHUB_API_BASE = "https://api.github.com"
JWT_EXPIRY_SECONDS = 9 * 60  # GitHub allows a max of 10 minutes
REQUEST_TIMEOUT_SECONDS = 15


class GitHubAuthError(Exception):
    pass


def create_app_jwt(app_id: str, private_key_pem: str) -> str:
    """Create the short-lived JWT used to authenticate as the GitHub App itself."""
    if not app_id or not private_key_pem:
        raise GitHubAuthError("GITHUB_APP_ID and GITHUB_PRIVATE_KEY must both be set.")

    now = int(time.time())
    payload = {
        "iat": now - 60,  # allow for clock drift
        "exp": now + JWT_EXPIRY_SECONDS,
        "iss": app_id,
    }
    try:
        return jwt.encode(payload, private_key_pem, algorithm="RS256")
    except (ValueError, jwt.InvalidKeyError) as exc:
        raise GitHubAuthError(f"Invalid GitHub App private key: {exc}") from exc


@dataclass
class InstallationToken:
    token: str
    expires_at: str


def get_installation_token(
    app_id: str,
    private_key_pem: str,
    installation_id: str,
    session: Optional[requests.Session] = None,
) -> InstallationToken:
    """Exchange the App JWT for an installation access token."""
    app_jwt = create_app_jwt(app_id, private_key_pem)
    session = session or requests.Session()

    url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        resp = session.post(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise GitHubAuthError(f"Failed to reach GitHub: {exc}") from exc

    if resp.status_code != 201:
        raise GitHubAuthError(
            f"GitHub rejected installation token request (status {resp.status_code}): {resp.text[:300]}"
        )

    data = resp.json()
    return InstallationToken(token=data["token"], expires_at=data["expires_at"])
