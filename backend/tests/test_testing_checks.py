from app.analysis.testing_checks import check_missing_tests
from app.services.diff_parser import parse_diff

DIFF_WITH_LOGIC = """diff --git a/src/pricing.py b/src/pricing.py
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
"""

DIFF_TRIVIAL_WRAPPER = """diff --git a/src/pricing.py b/src/pricing.py
--- a/src/pricing.py
+++ b/src/pricing.py
@@ -1,1 +1,3 @@
+def get_base_price(item):
+    return item.price
"""


def _file_diff(diff_text: str):
    files = parse_diff(diff_text)
    return next(iter(files.values()))


def test_flags_nontrivial_untested_function():
    fd = _file_diff(DIFF_WITH_LOGIC)
    findings = check_missing_tests(
        fd, test_file_touched_in_diff=False, existing_tests_reference_function=lambda name: False
    )
    assert len(findings) == 1
    assert "calculate_discount" in findings[0].title


def test_does_not_flag_trivial_wrapper():
    fd = _file_diff(DIFF_TRIVIAL_WRAPPER)
    findings = check_missing_tests(
        fd, test_file_touched_in_diff=False, existing_tests_reference_function=lambda name: False
    )
    assert findings == []


def test_does_not_flag_when_test_file_touched_in_same_pr():
    fd = _file_diff(DIFF_WITH_LOGIC)
    findings = check_missing_tests(
        fd, test_file_touched_in_diff=True, existing_tests_reference_function=lambda name: False
    )
    assert findings == []


def test_does_not_flag_when_existing_test_already_covers_function():
    fd = _file_diff(DIFF_WITH_LOGIC)
    findings = check_missing_tests(
        fd, test_file_touched_in_diff=False, existing_tests_reference_function=lambda name: True
    )
    assert findings == []


def test_skips_test_files_themselves():
    diff_text = """diff --git a/tests/test_pricing.py b/tests/test_pricing.py
--- a/tests/test_pricing.py
+++ b/tests/test_pricing.py
@@ -1,1 +1,3 @@
+def helper_build_cart():
+    if True:
+        return []
"""
    fd = _file_diff(diff_text)
    findings = check_missing_tests(
        fd, test_file_touched_in_diff=False, existing_tests_reference_function=lambda name: False
    )
    assert findings == []
