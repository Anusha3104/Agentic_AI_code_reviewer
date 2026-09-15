"""
CRUD helpers used by the API routes and the webhook handler. Kept as
plain functions taking a SQLAlchemy `Session` rather than a repository
class hierarchy -- simple and easy for a student to follow, per the
project's "Important Engineering Rule" (no unnecessary complexity).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import models
from app.models.finding import Finding as FindingSchema
from app.models.finding import ReviewResult


def get_or_create_repository(session: Session, github_repo_id: str, name: str, owner: str) -> models.Repository:
    existing = session.execute(
        select(models.Repository).where(models.Repository.github_repo_id == github_repo_id)
    ).scalar_one_or_none()
    if existing:
        return existing
    repo = models.Repository(github_repo_id=github_repo_id, name=name, owner=owner)
    session.add(repo)
    session.flush()
    return repo


def get_or_create_pull_request(
    session: Session,
    repository: models.Repository,
    github_pr_number: int,
    title: str,
    author: str,
    status: str = "open",
) -> models.PullRequest:
    existing = session.execute(
        select(models.PullRequest).where(
            models.PullRequest.repository_id == repository.id,
            models.PullRequest.github_pr_number == github_pr_number,
        )
    ).scalar_one_or_none()
    if existing:
        existing.status = status
        existing.title = title
        return existing

    pr = models.PullRequest(
        repository_id=repository.id,
        github_pr_number=github_pr_number,
        title=title,
        author=author,
        status=status,
    )
    session.add(pr)
    session.flush()
    return pr


def create_review(session: Session, pull_request: models.PullRequest, status: str = "queued") -> models.Review:
    review = models.Review(pull_request_id=pull_request.id, status=status)
    session.add(review)
    session.flush()
    return review


def save_review_result(session: Session, review: models.Review, result: ReviewResult) -> models.Review:
    """Persist a completed ReviewResult's summary + findings onto an existing Review row."""
    review.status = result.status.value
    review.summary = result.summary
    review.completed_at = datetime.now(timezone.utc)

    for f in result.findings:
        db_finding = models.Finding(
            review_id=review.id,
            file=f.file,
            line=f.line,
            category=f.category.value,
            severity=f.severity.value,
            confidence=f.confidence,
            title=f.title,
            description=f.description,
            suggestion=f.suggestion,
            validation_status=(
                "valid" if f.validated is True else "invalid" if f.validated is False else "unvalidated"
            ),
        )
        session.add(db_finding)

    session.flush()
    return review


def mark_review_failed(session: Session, review: models.Review, error_message: str) -> None:
    review.status = "failed"
    review.summary = f"Review failed: {error_message}"
    review.completed_at = datetime.now(timezone.utc)
    session.flush()


def get_review(session: Session, review_id: int) -> Optional[models.Review]:
    return session.get(models.Review, review_id)


def list_repositories(session: Session) -> list[models.Repository]:
    return list(session.execute(select(models.Repository)).scalars().all())


def list_pull_requests(session: Session) -> list[models.PullRequest]:
    return list(session.execute(select(models.PullRequest)).scalars().all())


def has_running_or_queued_review(session: Session, pull_request: models.PullRequest) -> bool:
    """Used to prevent duplicate processing of the same webhook delivery/PR state."""
    existing = session.execute(
        select(models.Review).where(
            models.Review.pull_request_id == pull_request.id,
            models.Review.status.in_(["queued", "running"]),
        )
    ).first()
    return existing is not None
