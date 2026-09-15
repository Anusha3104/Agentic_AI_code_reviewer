"""
Core data models shared across the whole system.

These mirror the JSON "Finding" contract described in the project spec.
Every analyzer (rule-based today, LLM-based from Phase 2 onward) must
produce objects that satisfy this schema, so the rest of the pipeline
(validation, filtering, review generation, storage) never needs to know
where a finding came from.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    CORRECTNESS = "correctness"
    SECURITY = "security"
    TESTING = "testing"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    REPOSITORY_CONSISTENCY = "repository_consistency"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Finding(BaseModel):
    """A single potential issue found in a PR diff."""

    file: str
    line: int = Field(..., ge=1)
    category: Category
    severity: Severity
    confidence: float = Field(..., ge=0.0, le=1.0)
    title: str
    description: str
    impact: str
    suggestion: str

    # Populated by the validation stage (Phase 6). Not required to build a
    # finding in Phase 1, but declared here now so the schema doesn't churn.
    validated: Optional[bool] = None
    validation_reason: Optional[str] = None

    # Which analyzer produced this finding. Useful for debugging/evaluation.
    source: str = "rule_based"

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 2)


class ReviewStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewResult(BaseModel):
    """The final output of a full review run over a PR diff."""

    status: ReviewStatus = ReviewStatus.COMPLETED
    files_reviewed: List[str] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    summary: str = ""
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_public_dict(self) -> dict:
        """Serialize using plain JSON-friendly types (used by the CLI)."""
        return {
            "status": self.status.value,
            "files_reviewed": self.files_reviewed,
            "summary": self.summary,
            "findings": [f.model_dump(mode="json") for f in self.findings],
            "generated_at": self.generated_at.isoformat(),
        }
