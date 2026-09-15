from app.services.diff_parser import parse_diff

SAMPLE_DIFF = """diff --git a/src/auth.py b/src/auth.py
index 1234567..89abcde 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,8 @@ def get_user(user_id):
     conn = get_connection()
-    query = "SELECT * FROM users WHERE id=" + str(user_id)
-    return conn.execute(query)
+    query = "SELECT * FROM users WHERE id=" + user_id
+    result = conn.execute(query)
+    return result
"""

NEW_FILE_DIFF = """diff --git a/src/new_module.py b/src/new_module.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/src/new_module.py
@@ -0,0 +1,3 @@
+def add(a, b):
+    return a + b
+
"""


def test_parse_diff_extracts_file_path():
    files = parse_diff(SAMPLE_DIFF)
    assert "src/auth.py" in files


def test_parse_diff_extracts_added_lines_with_correct_line_numbers():
    files = parse_diff(SAMPLE_DIFF)
    file_diff = files["src/auth.py"]
    added_contents = [al.content for al in file_diff.added_lines]
    assert any("SELECT * FROM users" in c for c in added_contents)
    # first added line should be at line 11 (hunk starts new-file at line 10)
    line_numbers = file_diff.added_line_numbers
    assert 11 in line_numbers


def test_parse_diff_handles_new_file():
    files = parse_diff(NEW_FILE_DIFF)
    file_diff = files["src/new_module.py"]
    assert file_diff.is_new_file is True
    assert len(file_diff.added_lines) == 3
    assert file_diff.added_lines[0].line_number == 1


def test_parse_diff_empty_input_returns_empty_dict():
    assert parse_diff("") == {}


def test_parse_diff_counts_removed_lines():
    files = parse_diff(SAMPLE_DIFF)
    file_diff = files["src/auth.py"]
    assert file_diff.removed_line_count == 2
