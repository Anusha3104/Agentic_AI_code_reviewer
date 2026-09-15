"""API-facing Pydantic schemas (separate from the internal Finding model
so the HTTP contract can evolve independently of the internal pipeline)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class FindingOut(BaseModel):
    id: int
    file: str
    line: int
    category: str
    severity: str
    confidence: float
    title: str
    description: str
    suggestion: str
    validation_status: str

    model_config = ConfigDict(from_attributes=True)


class ReviewOut(BaseModel):
    id: int
    pull_request_id: int
    status: str
    summary: str
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ReviewDetailOut(ReviewOut):
    findings: List[FindingOut] = []


class PullRequestOut(BaseModel):
    id: int
    repository_id: int
    github_pr_number: int
    title: str
    author: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoryOut(BaseModel):
    id: int
    github_repo_id: str
    name: str
    owner: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunReviewRequest(BaseModel):
    repo_path: Optional[str] = None
    diff_text: Optional[str] = None


class HealthOut(BaseModel):
    status: str = "ok"
