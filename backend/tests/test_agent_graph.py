from app.agents.graph import run_agent_review

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


def test_agent_review_detects_vulnerability_without_llm(tmp_path, monkeypatch):
    # No GEMINI_API_KEY configured -> llm_review_node no-ops, but the
    # deterministic + validation (pass-through) stages still run through
    # the full graph.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = run_agent_review(repo_path=str(tmp_path), diff_text=VULNERABLE_DIFF, use_llm=True)
    assert result.status.value == "completed"
    assert len(result.findings) >= 1
    assert any(f.category.value == "security" for f in result.findings)


def test_agent_review_no_findings_on_clean_diff(tmp_path):
    result = run_agent_review(repo_path=str(tmp_path), diff_text=CLEAN_DIFF, use_llm=True)
    assert result.findings == []
    assert "No high-confidence issues found" in result.summary


def test_agent_review_respects_min_confidence(tmp_path):
    result = run_agent_review(repo_path=str(tmp_path), diff_text=VULNERABLE_DIFF, min_confidence=1.01)
    assert result.findings == []


def test_agent_review_use_llm_false_skips_llm_entirely(tmp_path):
    result = run_agent_review(repo_path=str(tmp_path), diff_text=VULNERABLE_DIFF, use_llm=False)
    assert result.status.value == "completed"
    # still finds the deterministic SQL-injection pattern
    assert len(result.findings) >= 1


def test_agent_review_findings_marked_unvalidated_without_llm(tmp_path):
    result = run_agent_review(repo_path=str(tmp_path), diff_text=VULNERABLE_DIFF)
    assert len(result.findings) >= 1
    assert all(f.validated is None for f in result.findings)
