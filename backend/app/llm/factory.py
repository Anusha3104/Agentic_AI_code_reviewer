"""
Factory for obtaining the configured LLM provider.

Adding a new provider (Groq, OpenRouter, any OpenAI-compatible API) means:
  1. Implement `LLMProvider` in a new module under app/llm/.
  2. Add one `elif` branch here.
No other code in the project should ever import a provider class directly.
"""
from __future__ import annotations

from app.config import settings
from app.llm.base import LLMProvider


def get_llm_provider() -> LLMProvider | None:
    """
    Returns a configured LLMProvider, or None if no provider is usable
    (e.g. no API key set). Callers MUST handle the None case gracefully
    -- the system is designed to still run its deterministic checks with
    no LLM configured at all (see app/services/review_engine.py).
    """
    provider_name = (settings.llm_provider or "gemini").lower()

    if provider_name == "gemini":
        if not settings.gemini_api_key:
            return None
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(api_key=settings.gemini_api_key)

    # Extension points for future providers:
    # elif provider_name == "groq":
    #     from app.llm.groq_provider import GroqProvider
    #     return GroqProvider(api_key=settings.groq_api_key)
    # elif provider_name == "openrouter":
    #     from app.llm.openrouter_provider import OpenRouterProvider
    #     return OpenRouterProvider(api_key=settings.openrouter_api_key)

    raise ValueError(f"Unknown LLM_PROVIDER: {provider_name!r}")
