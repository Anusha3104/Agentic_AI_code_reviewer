from types import SimpleNamespace

import pytest

import app.llm.factory as factory_module
from app.llm.gemini_provider import GeminiProvider


def _patch_settings(monkeypatch, llm_provider="gemini", gemini_api_key=""):
    """
    Patch the `settings` object used inside app.llm.factory without
    touching real environment variables or reloading modules -- keeps
    each test fully isolated from the others.
    """
    fake_settings = SimpleNamespace(llm_provider=llm_provider, gemini_api_key=gemini_api_key)
    monkeypatch.setattr(factory_module, "settings", fake_settings)


def test_returns_none_when_no_api_key(monkeypatch):
    _patch_settings(monkeypatch, llm_provider="gemini", gemini_api_key="")
    assert factory_module.get_llm_provider() is None


def test_returns_gemini_provider_when_key_present(monkeypatch):
    _patch_settings(monkeypatch, llm_provider="gemini", gemini_api_key="fake-key")
    provider = factory_module.get_llm_provider()
    assert isinstance(provider, GeminiProvider)


def test_unknown_provider_raises(monkeypatch):
    _patch_settings(monkeypatch, llm_provider="not_a_real_provider", gemini_api_key="")
    with pytest.raises(ValueError):
        factory_module.get_llm_provider()
