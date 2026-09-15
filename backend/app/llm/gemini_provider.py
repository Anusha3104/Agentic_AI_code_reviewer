"""
Gemini provider -- talks to the Google AI Studio free-tier Gemini API
over plain HTTPS (no google-generativeai SDK dependency, to keep the
install footprint small and the request/response shape easy to mock in
tests).

Docs: https://ai.google.dev/gemini-api/docs
"""
from __future__ import annotations

import json
import logging
from typing import List

import requests

from app.llm.base import LLMError, LLMProvider
from app.llm.response_parsing import parse_json_response
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger("llm.gemini")

DEFAULT_MODEL = "gemini-2.5-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
REQUEST_TIMEOUT_SECONDS = 30


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, session: requests.Session | None = None):
        if not api_key:
            raise ValueError("GeminiProvider requires a non-empty api_key")
        self.api_key = api_key
        self.model = model
        self.session = session or requests.Session()

    def _call(self, system_prompt: str, user_content: str) -> str:
        url = f"{API_BASE}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {"temperature": 0.1},
        }
        try:
            resp = self.session.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            logger.error("gemini.request_failed", extra={"error": str(exc)})
            raise LLMError(f"Gemini request failed: {exc}") from exc

        if resp.status_code != 200:
            # Never log the API key; it's not in the response body or URL params we log.
            logger.error("gemini.non_200", extra={"status_code": resp.status_code})
            raise LLMError(f"Gemini API returned status {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMError(f"Unexpected Gemini response shape: {exc}") from exc

        return text

    def generate_review(self, file_path: str, diff_hunk: str, context: str = "") -> List[dict]:
        system_prompt = load_prompt("reviewer_prompt")
        user_content = (
            f"FILE: {file_path}\n\n"
            f"DIFF:\n{diff_hunk}\n\n"
            f"REPOSITORY CONTEXT:\n{context or '(none provided)'}"
        )
        raw = self._call(system_prompt, user_content)
        parsed = parse_json_response(raw)
        if not isinstance(parsed, list):
            raise LLMError(f"Expected a JSON array of findings, got: {type(parsed)}")
        return parsed

    def validate_finding(self, diff_context: str, finding: dict) -> dict:
        system_prompt = load_prompt("validator_prompt")
        user_content = (
            f"DIFF CONTEXT:\n{diff_context}\n\n"
            f"CANDIDATE FINDING:\n{json.dumps(finding, indent=2)}"
        )
        raw = self._call(system_prompt, user_content)
        parsed = parse_json_response(raw)
        if not isinstance(parsed, dict) or "valid" not in parsed:
            raise LLMError(f"Expected a validation object, got: {parsed!r}")
        return parsed

    def summarize_review(self, findings: List[dict], files_reviewed: int) -> str:
        system_prompt = load_prompt("summarizer_prompt")
        user_content = (
            f"Files reviewed: {files_reviewed}\n\n"
            f"Findings:\n{json.dumps(findings, indent=2)}"
        )
        return self._call(system_prompt, user_content).strip()
