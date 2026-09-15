import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.deps as deps_module
import app.api.webhooks as webhooks_module
import app.main as main_module
from app.database.base import Base

WEBHOOK_SECRET = "test-secret"


@pytest.fixture
def client(monkeypatch, tmp_path):
    """
    Isolate each test with its own in-memory-per-file SQLite database
    (via FastAPI dependency overrides, not module reloading -- reloading
    SQLAlchemy declarative models mid-suite causes metadata registry
    conflicts) and a fixed webhook secret.
    """
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    main_module.app.dependency_overrides[deps_module.get_db] = override_get_db

    fake_settings = SimpleNamespace(
        github_webhook_secret=WEBHOOK_SECRET,
        github_app_id="fake-app-id",
        github_private_key="fake-private-key",
    )
    monkeypatch.setattr(webhooks_module, "settings", fake_settings)

    with TestClient(main_module.app) as test_client:
        yield test_client

    main_module.app.dependency_overrides.clear()


def _sign(body: bytes) -> str:
    digest = hmac.new(WEBHOOK_SECRET.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_repositories_empty(client):
    resp = client.get("/api/repositories")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_pull_requests_empty(client):
    resp = client.get("/api/pull-requests")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_review_not_found(client):
    resp = client.get("/api/reviews/999")
    assert resp.status_code == 404


def test_get_pull_request_reviews_not_found(client):
    resp = client.get("/api/pull-requests/999/reviews")
    assert resp.status_code == 404


def test_get_pull_request_reviews_lists_reviews(client):
    payload = {
        "action": "opened",
        "pull_request": {"number": 99, "title": "T", "user": {"login": "carol"}, "state": "open"},
        "repository": {"full_name": "octo/repo"},
        "installation": {"id": 555},
    }
    body = json.dumps(payload).encode()

    with patch("app.api.webhooks.get_installation_token") as mock_token, \
         patch("app.api.webhooks.GitHubClient") as mock_client_cls:
        mock_token.return_value = MagicMock(token="fake-token")
        mock_client = MagicMock()
        mock_client.get_pr_diff.return_value = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,0 +1,1 @@\n+x=1\n"
        mock_client.post_review.return_value = {"id": 1}
        mock_client_cls.return_value = mock_client

        client.post(
            "/webhooks/github",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body), "X-GitHub-Event": "pull_request"},
        )

    prs = client.get("/api/pull-requests").json()
    pr = next(p for p in prs if p["github_pr_number"] == 99)
    reviews = client.get(f"/api/pull-requests/{pr['id']}/reviews")
    assert reviews.status_code == 200
    assert len(reviews.json()) == 1


def test_webhook_rejects_bad_signature(client):
    body = json.dumps({"action": "opened"}).encode()
    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "X-GitHub-Event": "pull_request"},
    )
    assert resp.status_code == 401


def test_webhook_ignores_non_pull_request_events(client):
    body = json.dumps({"zen": "keep it logically awesome"}).encode()
    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "X-GitHub-Event": "ping"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_ignores_irrelevant_pr_action(client):
    payload = {
        "action": "labeled",
        "pull_request": {"number": 1, "title": "T", "user": {"login": "alice"}, "state": "open"},
        "repository": {"full_name": "octo/repo"},
        "installation": {"id": 1},
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "X-GitHub-Event": "pull_request"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_full_flow_with_mocked_github(client):
    payload = {
        "action": "opened",
        "pull_request": {"number": 7, "title": "Add feature", "user": {"login": "alice"}, "state": "open"},
        "repository": {"full_name": "octo/repo"},
        "installation": {"id": 555},
    }
    body = json.dumps(payload).encode()

    sample_diff = (
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1,1 +1,2 @@\n"
        "+def add(a, b):\n"
        "+    return a + b\n"
    )

    with patch("app.api.webhooks.get_installation_token") as mock_token, \
         patch("app.api.webhooks.GitHubClient") as mock_client_cls:
        mock_token.return_value = MagicMock(token="fake-token")
        mock_client = MagicMock()
        mock_client.get_pr_diff.return_value = sample_diff
        mock_client.post_review.return_value = {"id": 1}
        mock_client_cls.return_value = mock_client

        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body), "X-GitHub-Event": "pull_request"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    mock_client.post_review.assert_called_once()

    review_resp = client.get(f"/api/reviews/{data['review_id']}")
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "completed"


def test_webhook_skips_duplicate_in_flight_review(client):
    payload = {
        "action": "opened",
        "pull_request": {"number": 8, "title": "T", "user": {"login": "bob"}, "state": "open"},
        "repository": {"full_name": "octo/repo"},
        "installation": {"id": 555},
    }
    body = json.dumps(payload).encode()

    with patch("app.api.webhooks.get_installation_token") as mock_token, \
         patch("app.api.webhooks.GitHubClient") as mock_client_cls:
        mock_token.return_value = MagicMock(token="fake-token")
        mock_client = MagicMock()
        mock_client.get_pr_diff.return_value = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,0 +1,1 @@\n+x=1\n"
        mock_client.post_review.return_value = {"id": 1}
        mock_client_cls.return_value = mock_client

        first = client.post(
            "/webhooks/github",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body), "X-GitHub-Event": "pull_request"},
        )
        assert first.status_code == 200
        assert first.json()["status"] == "completed"
