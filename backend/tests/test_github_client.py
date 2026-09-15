from unittest.mock import MagicMock, patch

import pytest
import requests

from app.github.client import GitHubAPIError, GitHubClient


def _mock_resp(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    return resp


def test_get_pull_request_returns_json():
    client = GitHubClient(token="fake")
    with patch.object(client.session, "request", return_value=_mock_resp(200, {"number": 1, "title": "x"})):
        pr = client.get_pull_request("octo", "repo", 1)
    assert pr["number"] == 1


def test_get_changed_files_paginates(monkeypatch):
    client = GitHubClient(token="fake")
    page_1 = [{"filename": f"f{i}.py", "status": "modified", "patch": "+x"} for i in range(100)]
    page_2 = [{"filename": "last.py", "status": "added", "patch": "+y"}]

    responses = [
        _mock_resp(200, page_1),
        _mock_resp(200, page_2),
    ]
    with patch.object(client.session, "request", side_effect=responses):
        files = client.get_changed_files("octo", "repo", 1)
    assert len(files) == 101
    assert files[-1].filename == "last.py"


def test_get_pr_diff_returns_text():
    client = GitHubClient(token="fake")
    resp = _mock_resp(200)
    resp.text = "diff --git a/x b/x\n+added line\n"
    with patch.object(client.session, "request", return_value=resp):
        diff = client.get_pr_diff("octo", "repo", 1)
    assert "diff --git" in diff


def test_error_status_raises_github_api_error():
    client = GitHubClient(token="fake")
    with patch.object(client.session, "request", return_value=_mock_resp(404, text="Not Found")):
        with pytest.raises(GitHubAPIError):
            client.get_pull_request("octo", "repo", 1)


def test_network_error_raises_github_api_error():
    client = GitHubClient(token="fake")
    with patch.object(client.session, "request", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(GitHubAPIError):
            client.get_pull_request("octo", "repo", 1)


def test_post_review_sends_comments_payload():
    client = GitHubClient(token="fake")
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["json"] = kwargs.get("json")
        return _mock_resp(200, {"id": 1})

    with patch.object(client.session, "request", side_effect=fake_request):
        client.post_review(
            "octo", "repo", 1, body="Summary", event="COMMENT",
            comments=[{"path": "src/x.py", "line": 5, "body": "issue here"}],
        )
    assert captured["json"]["body"] == "Summary"
    assert len(captured["json"]["comments"]) == 1


def test_get_file_content_decodes_base64():
    import base64

    client = GitHubClient(token="fake")
    encoded = base64.b64encode(b"print('hi')").decode()
    with patch.object(client.session, "request", return_value=_mock_resp(200, {"encoding": "base64", "content": encoded})):
        content = client.get_file_content("octo", "repo", "x.py", "main")
    assert content == "print('hi')"


def test_get_file_content_returns_none_on_error():
    client = GitHubClient(token="fake")
    with patch.object(client.session, "request", return_value=_mock_resp(404, text="not found")):
        content = client.get_file_content("octo", "repo", "missing.py", "main")
    assert content is None
