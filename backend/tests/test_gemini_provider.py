import json
from unittest.mock import MagicMock, patch

import pytest

from app.llm.base import LLMError
from app.llm.gemini_provider import GeminiProvider


def _mock_response(text: str, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = text
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }
    return mock_resp


def test_generate_review_parses_json_array():
    provider = GeminiProvider(api_key="fake-key")
    findings_json = json.dumps(
        [
            {
                "file": "src/auth.py",
                "line": 5,
                "category": "security",
                "severity": "high",
                "confidence": 0.9,
                "title": "SQL injection",
                "description": "d",
                "impact": "i",
                "suggestion": "s",
            }
        ]
    )
    with patch.object(provider.session, "post", return_value=_mock_response(findings_json)):
        result = provider.generate_review("src/auth.py", "+ some diff")
    assert len(result) == 1
    assert result[0]["file"] == "src/auth.py"


def test_generate_review_strips_markdown_fences():
    provider = GeminiProvider(api_key="fake-key")
    fenced = "```json\n[]\n```"
    with patch.object(provider.session, "post", return_value=_mock_response(fenced)):
        result = provider.generate_review("src/x.py", "+ diff")
    assert result == []


def test_generate_review_raises_llm_error_on_bad_json():
    provider = GeminiProvider(api_key="fake-key")
    with patch.object(provider.session, "post", return_value=_mock_response("not json at all")):
        with pytest.raises(LLMError):
            provider.generate_review("src/x.py", "+ diff")


def test_generate_review_raises_on_non_200():
    provider = GeminiProvider(api_key="fake-key")
    with patch.object(provider.session, "post", return_value=_mock_response("", status_code=500)):
        with pytest.raises(LLMError):
            provider.generate_review("src/x.py", "+ diff")


def test_validate_finding_parses_object():
    provider = GeminiProvider(api_key="fake-key")
    validation_json = json.dumps({"valid": True, "confidence": 0.95, "reason": "real issue"})
    with patch.object(provider.session, "post", return_value=_mock_response(validation_json)):
        result = provider.validate_finding("diff context", {"title": "x"})
    assert result["valid"] is True
    assert result["confidence"] == 0.95


def test_summarize_review_returns_plain_text():
    provider = GeminiProvider(api_key="fake-key")
    with patch.object(provider.session, "post", return_value=_mock_response("All good, no issues.")):
        summary = provider.summarize_review([], files_reviewed=3)
    assert "no issues" in summary.lower() or "All good" in summary


def test_missing_api_key_raises_value_error():
    with pytest.raises(ValueError):
        GeminiProvider(api_key="")


def test_request_exception_raises_llm_error():
    import requests

    provider = GeminiProvider(api_key="fake-key")
    with patch.object(provider.session, "post", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(LLMError):
            provider.generate_review("src/x.py", "+ diff")
