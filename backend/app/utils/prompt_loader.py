"""
Loads prompt templates from the top-level `prompts/` directory so that
LLM prompts are never hard-coded inline in Python modules (per project
convention -- see DEVELOPMENT.md).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load prompts/<name>.txt (without extension) as a string."""
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
