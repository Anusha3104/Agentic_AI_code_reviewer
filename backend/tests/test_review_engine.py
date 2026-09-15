from app.services.review_engine import run_review

VULNERABLE_DIFF = """diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -1,2 +1,3 @@
+def get_user(user_id):
+    query = "SELECT * FROM users WHERE id=" + user_id
+    return db.execute(query)
"""

CLEAN_DIFF = """diff --git a/src/math_utils.py b/src/math_utils.py
--- a/src/math_utils.py
+++ b/src/math_utils.py
@@ -1,2 +1,3 @@
+def multiply(a, b):
+    return a * b
"""


def test_run_review_returns_findings_for_vulnerable_diff(tmp_path):
    result = run_review(repo_path=str(tmp_path), diff_text=VULNERABLE_DIFF)
    assert result.status.value == "completed"
    assert len(result.findings) >= 1
    assert result.findings[0].category.value == "security"
    assert "1" in result.summary


def test_run_review_reports_no_issues_for_clean_diff(tmp_path):
    result = run_review(repo_path=str(tmp_path), diff_text=CLEAN_DIFF)
    assert result.findings == []
    assert "No high-confidence issues found" in result.summary


def test_run_review_respects_confidence_threshold(tmp_path):
    # Setting an impossibly high threshold should filter out everything.
    result = run_review(repo_path=str(tmp_path), diff_text=VULNERABLE_DIFF, min_confidence=1.01)
    assert result.findings == []


def test_run_review_handles_missing_repo_path_gracefully(tmp_path):
    missing_repo = str(tmp_path / "does-not-exist")
    result = run_review(repo_path=missing_repo, diff_text=VULNERABLE_DIFF)
    # Should still run analysis on the diff itself without crashing.
    assert result.status.value == "completed"
    assert len(result.findings) >= 1
