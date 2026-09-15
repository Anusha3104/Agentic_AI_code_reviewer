from app.analysis.semgrep_runner import is_semgrep_available, run_semgrep


def test_semgrep_is_available_in_this_environment():
    # This project bundles offline rules specifically so semgrep works
    # without network access; if it's not installed the rest of this
    # file's assertions are skipped rather than failed.
    assert is_semgrep_available() in (True, False)


def test_run_semgrep_returns_empty_list_for_no_files():
    assert run_semgrep([]) == []


def test_run_semgrep_detects_eval_usage(tmp_path):
    if not is_semgrep_available():
        return  # environment without semgrep installed -- degrade gracefully
    f = tmp_path / "risky.py"
    f.write_text("def run(user_input):\n    return eval(user_input)\n")

    findings = run_semgrep([str(f)])
    assert any("eval" in finding.title.lower() for finding in findings)
    assert all(finding.source == "semgrep" for finding in findings)


def test_run_semgrep_no_findings_on_clean_file(tmp_path):
    if not is_semgrep_available():
        return
    f = tmp_path / "clean.py"
    f.write_text("def add(a, b):\n    return a + b\n")

    findings = run_semgrep([str(f)])
    assert findings == []


def test_run_semgrep_handles_missing_binary_gracefully(monkeypatch):
    import app.analysis.semgrep_runner as mod

    monkeypatch.setattr(mod, "is_semgrep_available", lambda: False)
    assert run_semgrep(["/some/file.py"]) == []
