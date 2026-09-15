"""
LLM provider abstraction.

Every LLM backend (Gemini today; Groq / OpenRouter / any OpenAI-compatible
API later) implements this interface. Nothing outside `app/llm/` should
ever import a provider-specific SDK or know which provider is active --
callers get an `LLMProvider` from `get_llm_provider()` (see factory.py)
and use only these three methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class LLMError(Exception):
    """Raised when an LLM call fails or returns an unusable response."""


class LLMProvider(ABC):
    @abstractmethod
    def generate_review(self, file_path: str, diff_hunk: str, context: str = "") -> List[dict]:
        """
        Ask the model to review a single file's diff hunk.

        Returns a list of finding dicts matching the Finding schema
        (see app/models/finding.py). Returns [] if the model reports no
        issues. Raises LLMError on failure (network error, malformed
        response, etc.) -- callers decide how to degrade gracefully.
        """

    @abstractmethod
    def validate_finding(self, diff_context: str, finding: dict) -> dict:
        """
        Ask the model to validate a single candidate finding.

        Returns {"valid": bool, "confidence": float, "reason": str}.
        Raises LLMError on failure.
        """

    @abstractmethod
    def summarize_review(self, findings: List[dict], files_reviewed: int) -> str:
        """
        Ask the model for a short natural-language summary of the review.

        Returns a plain-text string. Raises LLMError on failure.
        """
