from app.analysis.rule_based_checks import run_rule_based_checks
from app.services.diff_parser import parse_diff

SQL_INJECTION_DIFF = """diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -1,2 +1,3 @@
+def get_user(user_id):
+    query = "SELECT * FROM users WHERE id=" + user_id
+    return db.execute(query)
"""

CLEAN_DIFF = """diff --git a/src/utils.py b/src/utils.py
--- a/src/utils.py
+++ b/src/utils.py
@@ -1,2 +1,3 @@
+def add(a, b):
+    return a + b
"""

HARDCODED_SECRET_DIFF = """diff --git a/src/config.py b/src/config.py
--- a/src/config.py
+++ b/src/config.py
@@ -1,1 +1,2 @@
+api_key = "demo_secret_notreal_abcdefg123456789xyz"
"""

SAFE_SECRET_DIFF = """diff --git a/src/config.py b/src/config.py
--- a/src/config.py
+++ b/src/config.py
@@ -1,1 +1,2 @@
+api_key = os.environ.get("API_KEY")
"""

BARE_EXCEPT_DIFF = """diff --git a/src/worker.py b/src/worker.py
--- a/src/worker.py
+++ b/src/worker.py
@@ -1,3 +1,5 @@
+try:
+    do_something()
+except:
+    pass
"""

OFF_BY_ONE_DIFF = """diff --git a/src/list_utils.py b/src/list_utils.py
--- a/src/list_utils.py
+++ b/src/list_utils.py
@@ -1,2 +1,3 @@
+def last(items):
+    return items[len(items)]
"""

COMMAND_INJECTION_DIFF = """diff --git a/src/tools.py b/src/tools.py
--- a/src/tools.py
+++ b/src/tools.py
@@ -1,2 +1,3 @@
+def ping(host):
+    os.system("ping -c 1 " + host)
"""


def _findings_for(diff_text: str):
    files = parse_diff(diff_text)
    all_findings = []
    for file_diff in files.values():
        all_findings.extend(run_rule_based_checks(file_diff))
    return all_findings


def test_sql_injection_detected():
    findings = _findings_for(SQL_INJECTION_DIFF)
    assert any(f.category.value == "security" and "SQL" in f.title for f in findings)


def test_clean_code_produces_no_findings():
    findings = _findings_for(CLEAN_DIFF)
    assert findings == []


def test_hardcoded_secret_detected():
    findings = _findings_for(HARDCODED_SECRET_DIFF)
    assert any("secret" in f.title.lower() for f in findings)


def test_env_based_secret_not_flagged():
    findings = _findings_for(SAFE_SECRET_DIFF)
    assert findings == []


def test_bare_except_detected():
    findings = _findings_for(BARE_EXCEPT_DIFF)
    assert any("except" in f.title.lower() for f in findings)


def test_off_by_one_detected():
    findings = _findings_for(OFF_BY_ONE_DIFF)
    assert any("off-by-one" in f.title.lower() or "index" in f.title.lower() for f in findings)


def test_command_injection_detected():
    findings = _findings_for(COMMAND_INJECTION_DIFF)
    assert any("command injection" in f.title.lower() for f in findings)


def test_non_python_file_is_skipped():
    diff_text = """diff --git a/src/query.sql b/src/query.sql
--- a/src/query.sql
+++ b/src/query.sql
@@ -1,1 +1,2 @@
+SELECT * FROM users WHERE id = '1' + user_id
"""
    findings = _findings_for(diff_text)
    assert findings == []
