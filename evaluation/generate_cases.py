"""
One-time generator for the evaluation dataset. Run this to (re)create the
JSON case files in test_cases/ and expected_findings/. Kept as a script
(rather than hand-editing 30+ JSON files) so new cases are easy to add --
just append to CASES below and re-run.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "test_cases"
EXPECTED_DIR = HERE / "expected_findings"

# Each case: id, description, category (informational), diff, repo_files
# (materialized on disk before running the reviewer), and either
# expected_categories (list of categories that MUST appear at least once
# in the findings) or expect_no_findings=True (the reviewer must produce
# zero findings for this diff).
CASES = [
    # ---------------- SHOULD FLAG: correctness ----------------
    {
        "id": "correctness_off_by_one",
        "description": "Indexing a list with len(items) is always out of range.",
        "category": "correctness",
        "repo_files": {},
        "diff": """diff --git a/src/list_utils.py b/src/list_utils.py
--- a/src/list_utils.py
+++ b/src/list_utils.py
@@ -1,1 +1,3 @@
+def last_item(items):
+    return items[len(items)]
""",
        "expected_categories": ["correctness"],
    },
    {
        "id": "correctness_bare_except",
        "description": "Bare except: swallows all exceptions including KeyboardInterrupt.",
        "category": "correctness",
        "repo_files": {},
        "diff": """diff --git a/src/worker.py b/src/worker.py
--- a/src/worker.py
+++ b/src/worker.py
@@ -1,1 +1,5 @@
+def process(job):
+    try:
+        job.run()
+    except:
+        pass
""",
        "expected_categories": ["correctness"],
    },
    # ---------------- SHOULD FLAG: security ----------------
    {
        "id": "security_sql_injection",
        "description": "SQL query built via string concatenation with user input.",
        "category": "security",
        "repo_files": {},
        "diff": """diff --git a/src/user_service.py b/src/user_service.py
--- a/src/user_service.py
+++ b/src/user_service.py
@@ -1,1 +1,3 @@
+def get_user(user_id):
+    query = "SELECT * FROM users WHERE id=" + user_id
+    return db.execute(query)
""",
        "expected_categories": ["security"],
    },
    {
        "id": "security_command_injection",
        "description": "os.system called with a concatenated, user-influenced string.",
        "category": "security",
        "repo_files": {},
        "diff": """diff --git a/src/tools.py b/src/tools.py
--- a/src/tools.py
+++ b/src/tools.py
@@ -1,1 +1,3 @@
+def ping(host):
+    import os
+    os.system("ping -c 1 " + host)
""",
        "expected_categories": ["security"],
    },
    {
        "id": "security_hardcoded_secret",
        "description": "A live-looking API key is hardcoded as a literal string.",
        "category": "security",
        "repo_files": {},
        "diff": """diff --git a/src/config.py b/src/config.py
--- a/src/config.py
+++ b/src/config.py
@@ -1,1 +1,2 @@
+STRIPE_API_KEY = "demo_secret_notreal_abcdefg123456789xyz"
""",
        "expected_categories": ["security"],
    },
    {
        "id": "security_pickle_deserialization",
        "description": "pickle.loads() on data that may come from an untrusted source.",
        "category": "security",
        "repo_files": {},
        "diff": """diff --git a/src/cache.py b/src/cache.py
--- a/src/cache.py
+++ b/src/cache.py
@@ -1,1 +1,3 @@
+import pickle
+def load_cached(data):
+    return pickle.loads(data)
""",
        "expected_categories": ["security"],
    },
    {
        "id": "security_unsafe_yaml_load",
        "description": "yaml.load() without a safe loader can construct arbitrary objects.",
        "category": "security",
        "repo_files": {},
        "diff": """diff --git a/src/config_loader.py b/src/config_loader.py
--- a/src/config_loader.py
+++ b/src/config_loader.py
@@ -1,1 +1,3 @@
+import yaml
+def load_config(raw):
+    return yaml.load(raw)
""",
        "expected_categories": ["security"],
    },
    {
        "id": "security_eval_usage",
        "description": "eval() called on a function argument (semgrep-detected).",
        "category": "security",
        "repo_files": {},
        "diff": """diff --git a/src/calculator.py b/src/calculator.py
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -1,1 +1,2 @@
+def compute(expr):
+    return eval(expr)
""",
        "expected_categories": ["security"],
    },
    {
        "id": "security_subprocess_shell_true",
        "description": "subprocess call with shell=True (semgrep-detected).",
        "category": "security",
        "repo_files": {},
        "diff": """diff --git a/src/runner.py b/src/runner.py
--- a/src/runner.py
+++ b/src/runner.py
@@ -1,1 +1,3 @@
+import subprocess
+def run(cmd):
+    subprocess.run(cmd, shell=True)
""",
        "expected_categories": ["security"],
    },
    {
        "id": "security_flask_debug_true",
        "description": "Flask app run with debug=True exposes the interactive debugger (semgrep-detected).",
        "category": "security",
        "repo_files": {},
        "diff": """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,1 +1,3 @@
+from flask import Flask
+app = Flask(__name__)
+app.run(debug=True)
""",
        "expected_categories": ["security"],
    },
    # ---------------- SHOULD FLAG: testing ----------------
    {
        "id": "testing_missing_test_for_new_logic",
        "description": "New function with real branching logic and no accompanying test.",
        "category": "testing",
        "repo_files": {},
        "diff": """diff --git a/src/pricing.py b/src/pricing.py
--- a/src/pricing.py
+++ b/src/pricing.py
@@ -1,1 +1,8 @@
+def calculate_discount(price, coupon):
+    if coupon == "SAVE10":
+        return price * 0.9
+    elif coupon == "SAVE20":
+        return price * 0.8
+    else:
+        return price
""",
        "expected_categories": ["testing"],
    },
    # ---------------- SHOULD NOT FLAG: legitimate code ----------------
    {
        "id": "clean_parameterized_query",
        "description": "SQL query using a parameterized placeholder -- not injectable.",
        "repo_files": {},
        "diff": """diff --git a/src/user_service.py b/src/user_service.py
--- a/src/user_service.py
+++ b/src/user_service.py
@@ -1,1 +1,3 @@
+def get_user(user_id):
+    query = "SELECT * FROM users WHERE id = %s"
+    return db.execute(query, (user_id,))
""",
        "expect_no_findings": True,
    },
    {
        "id": "clean_env_based_secret",
        "description": "Secret loaded from an environment variable, not hardcoded.",
        "repo_files": {},
        "diff": """diff --git a/src/config.py b/src/config.py
--- a/src/config.py
+++ b/src/config.py
@@ -1,1 +1,3 @@
+import os
+STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")
""",
        "expect_no_findings": True,
    },
    {
        "id": "clean_specific_except",
        "description": "Exception handling that catches a specific, expected exception type, with its own test included in the same PR.",
        "repo_files": {},
        "diff": """diff --git a/src/worker.py b/src/worker.py
--- a/src/worker.py
+++ b/src/worker.py
@@ -1,1 +1,5 @@
+def process(job):
+    try:
+        job.run()
+    except TimeoutError:
+        logger.warning("job timed out")
diff --git a/tests/test_worker.py b/tests/test_worker.py
--- a/tests/test_worker.py
+++ b/tests/test_worker.py
@@ -1,1 +1,3 @@
+def test_process_handles_timeout():
+    process(TimeoutJob())
""",
        "expect_no_findings": True,
    },
    {
        "id": "clean_trivial_wrapper_no_test_needed",
        "description": "A trivial one-line getter shouldn't be flagged as needing a test.",
        "repo_files": {},
        "diff": """diff --git a/src/pricing.py b/src/pricing.py
--- a/src/pricing.py
+++ b/src/pricing.py
@@ -1,1 +1,3 @@
+def get_base_price(item):
+    return item.price
""",
        "expect_no_findings": True,
    },
    {
        "id": "clean_safe_yaml_load",
        "description": "yaml.safe_load() is the secure variant and should not be flagged.",
        "repo_files": {},
        "diff": """diff --git a/src/config_loader.py b/src/config_loader.py
--- a/src/config_loader.py
+++ b/src/config_loader.py
@@ -1,1 +1,3 @@
+import yaml
+def load_config(raw):
+    return yaml.safe_load(raw)
""",
        "expect_no_findings": True,
    },
    {
        "id": "clean_correct_indexing",
        "description": "Correct use of len(items) - 1 for the last index.",
        "repo_files": {},
        "diff": """diff --git a/src/list_utils.py b/src/list_utils.py
--- a/src/list_utils.py
+++ b/src/list_utils.py
@@ -1,1 +1,3 @@
+def last_item(items):
+    return items[len(items) - 1]
""",
        "expect_no_findings": True,
    },
    {
        "id": "clean_simple_arithmetic_function",
        "description": "A simple, correct arithmetic helper with no security/correctness issues.",
        "repo_files": {},
        "diff": """diff --git a/src/math_utils.py b/src/math_utils.py
--- a/src/math_utils.py
+++ b/src/math_utils.py
@@ -1,1 +1,3 @@
+def multiply(a, b):
+    return a * b
""",
        "expect_no_findings": True,
    },
    {
        "id": "clean_test_file_change_not_flagged_for_missing_tests",
        "description": "Changing a test file itself should never trigger a missing-test finding.",
        "repo_files": {},
        "diff": """diff --git a/tests/test_pricing.py b/tests/test_pricing.py
--- a/tests/test_pricing.py
+++ b/tests/test_pricing.py
@@ -1,1 +1,4 @@
+def test_calculate_discount():
+    if True:
+        assert calculate_discount(100, "SAVE10") == 90
""",
        "expect_no_findings": True,
    },
]


def main():
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    for case in CASES:
        case_path = CASES_DIR / f"{case['id']}.json"
        case_path.write_text(json.dumps({
            "id": case["id"],
            "description": case["description"],
            "diff": case["diff"],
            "repo_files": case.get("repo_files", {}),
        }, indent=2))

        expected = {
            "id": case["id"],
            "expect_no_findings": case.get("expect_no_findings", False),
            "expected_categories": case.get("expected_categories", []),
        }
        (EXPECTED_DIR / f"{case['id']}.json").write_text(json.dumps(expected, indent=2))

    print(f"Wrote {len(CASES)} test cases to {CASES_DIR} and {EXPECTED_DIR}")


if __name__ == "__main__":
    main()
