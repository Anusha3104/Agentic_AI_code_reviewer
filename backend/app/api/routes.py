from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    FindingOut,
    HealthOut,
    PullRequestOut,
    RepositoryOut,
    ReviewDetailOut,
    ReviewOut,
)
from app.database import crud

logger = logging.getLogger("api.routes")

router = APIRouter()


@router.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/api/repositories", response_model=list[RepositoryOut])
def list_repositories(db: Session = Depends(get_db)):
    return crud.list_repositories(db)


@router.get("/api/pull-requests", response_model=list[PullRequestOut])
def list_pull_requests(db: Session = Depends(get_db)):
    return crud.list_pull_requests(db)


@router.get("/api/reviews/{review_id}", response_model=ReviewOut)
def get_review(review_id: int, db: Session = Depends(get_db)):
    review = crud.get_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.get("/api/reviews/{review_id}/findings", response_model=list[FindingOut])
def get_review_findings(review_id: int, db: Session = Depends(get_db)):
    review = crud.get_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review.findings


@router.get("/api/pull-requests/{pr_id}/reviews", response_model=list[ReviewOut])
def get_pull_request_reviews(pr_id: int, db: Session = Depends(get_db)):
    from app.database import models

    pr = db.get(models.PullRequest, pr_id)
    if pr is None:
        raise HTTPException(status_code=404, detail="Pull request not found")
    return pr.reviews


@router.post("/api/reviews/{pr_id}/run", response_model=ReviewDetailOut)
def run_review_for_pr(pr_id: int, db: Session = Depends(get_db)):
    """
    Re-run a review for an already-known PullRequest row using local
    Development Mode semantics (no live GitHub fetch here -- that's
    handled by the webhook flow in app/api/webhooks.py). This endpoint
    exists mainly so the dashboard can trigger a manual re-run.
    """
    from app.database import models

    pr = db.get(models.PullRequest, pr_id)
    if pr is None:
        raise HTTPException(status_code=404, detail="Pull request not found")

    review = crud.create_review(db, pr, status="running")
    db.flush()

    try:
        # In local/dashboard-triggered mode we don't have a live diff
        # source without GitHub credentials, so this is a clearly
        # documented no-op result rather than a silent failure.
        from app.models.finding import ReviewResult, ReviewStatus

        result = ReviewResult(
            status=ReviewStatus.COMPLETED,
            files_reviewed=[],
            findings=[],
            summary=(
                "Manual re-run requested, but no live diff source is configured "
                "for this endpoint outside the GitHub webhook flow. Use the "
                "GitHub webhook (pull_request.synchronize) or the local CLI "
                "(review.py) to generate a real review."
            ),
        )
        crud.save_review_result(db, review, result)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("api.run_review_failed", extra={"pr_id": pr_id, "error": str(exc)})
        crud.mark_review_failed(db, review, str(exc))

    db.flush()
    db.refresh(review)
    return review
