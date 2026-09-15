"""
Helpers shared by every LLM provider for turning a model's raw text
response into structured Python data, tolerating the common ways models
deviate from "respond with only JSON" (markdown code fences, leading/
trailing prose).
"""
from __future__ import annotations

import json
import re

from app.llm.base import LLMError

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def strip_code_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def parse_json_response(text: str) -> "dict | list":
    cleaned = strip_code_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: try to find the first {...} or [...] block.
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        raise LLMError(f"Model response was not valid JSON: {text[:200]!r}")
