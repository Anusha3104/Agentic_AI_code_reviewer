import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import crud
from app.database.base import Base
from app.database import models
from app.models.finding import Category, Finding, ReviewResult, ReviewStatus, Severity


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_or_create_repository_creates_once(db_session):
    repo1 = crud.get_or_create_repository(db_session, "gh-1", "hello-world", "octocat")
    repo2 = crud.get_or_create_repository(db_session, "gh-1", "hello-world", "octocat")
    assert repo1.id == repo2.id


def test_get_or_create_pull_request_updates_existing(db_session):
    repo = crud.get_or_create_repository(db_session, "gh-1", "hello-world", "octocat")
    pr1 = crud.get_or_create_pull_request(db_session, repo, 42, "Initial title", "alice")
    pr2 = crud.get_or_create_pull_request(db_session, repo, 42, "Updated title", "alice")
    assert pr1.id == pr2.id
    assert pr2.title == "Updated title"


def test_save_review_result_persists_findings(db_session):
    repo = crud.get_or_create_repository(db_session, "gh-1", "hello-world", "octocat")
    pr = crud.get_or_create_pull_request(db_session, repo, 1, "T", "alice")
    review = crud.create_review(db_session, pr)

    result = ReviewResult(
        status=ReviewStatus.COMPLETED,
        files_reviewed=["src/auth.py"],
        findings=[
            Finding(
                file="src/auth.py",
                line=5,
                category=Category.SECURITY,
                severity=Severity.HIGH,
                confidence=0.9,
                title="SQL injection",
                description="d",
                impact="i",
                suggestion="s",
                validated=True,
            )
        ],
        summary="Reviewed 1 file, found 1 issue.",
    )
    crud.save_review_result(db_session, review, result)

    fetched = crud.get_review(db_session, review.id)
    assert fetched.status == "completed"
    assert len(fetched.findings) == 1
    assert fetched.findings[0].validation_status == "valid"


def test_mark_review_failed(db_session):
    repo = crud.get_or_create_repository(db_session, "gh-1", "hello-world", "octocat")
    pr = crud.get_or_create_pull_request(db_session, repo, 1, "T", "alice")
    review = crud.create_review(db_session, pr)

    crud.mark_review_failed(db_session, review, "GitHub API timed out")
    assert review.status == "failed"
    assert "timed out" in review.summary


def test_has_running_or_queued_review_detects_duplicate(db_session):
    repo = crud.get_or_create_repository(db_session, "gh-1", "hello-world", "octocat")
    pr = crud.get_or_create_pull_request(db_session, repo, 1, "T", "alice")
    assert crud.has_running_or_queued_review(db_session, pr) is False

    crud.create_review(db_session, pr, status="running")
    assert crud.has_running_or_queued_review(db_session, pr) is True


def test_list_repositories_and_pull_requests(db_session):
    repo = crud.get_or_create_repository(db_session, "gh-1", "hello-world", "octocat")
    crud.get_or_create_pull_request(db_session, repo, 1, "T", "alice")
    assert len(crud.list_repositories(db_session)) == 1
    assert len(crud.list_pull_requests(db_session)) == 1
