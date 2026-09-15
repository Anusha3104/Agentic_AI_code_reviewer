"""
Application configuration.

All configuration is loaded from environment variables (optionally via a
.env file). Nothing here should ever contain a hard-coded secret.

Phase 1 only needs a handful of these values. Later phases (GitHub App,
database, etc.) will use the rest, but we define them all now so the
shape of the configuration is stable as the project grows.
"""
import os
from dataclasses import dataclass
from pathlib import Path

# Load a local .env file if python-dotenv is available. This is optional so
# that Phase 1 (which has almost no dependencies) still works without it.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is an optional convenience
    pass


def _get_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- LLM provider (used from Phase 2 onward) ---
    llm_provider: str = os.environ.get("LLM_PROVIDER", "gemini")
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")

    # --- GitHub integration (used from Phase 7 onward) ---
    github_app_id: str = os.environ.get("GITHUB_APP_ID", "")
    github_private_key: str = os.environ.get("GITHUB_PRIVATE_KEY", "")
    github_webhook_secret: str = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

    # --- Database (used from Phase 8 onward) ---
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")

    # --- Review behavior (used starting Phase 1) ---
    min_confidence: float = _get_float("MIN_CONFIDENCE", 0.80)
    max_files_per_review: int = _get_int("MAX_FILES_PER_REVIEW", 20)
    max_tokens_per_review: int = _get_int("MAX_TOKENS_PER_REVIEW", 8000)
    test_timeout_seconds: int = _get_int("TEST_TIMEOUT_SECONDS", 120)

    # --- Paths ---
    project_root: Path = Path(__file__).resolve().parents[2]


settings = Settings()
