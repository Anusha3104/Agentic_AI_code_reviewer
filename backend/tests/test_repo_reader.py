import subprocess

import pytest

from app.services.repo_reader import RepositoryReader


@pytest.fixture
def sample_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text(
        "def validate_token(token):\n    return token == 'secret'\n"
    )
    (tmp_path / "src" / "test_auth.py").write_text(
        "def test_validate_token():\n    assert True\n"
    )
    (tmp_path / "src" / "unrelated.py").write_text("x = 1\n")
    return tmp_path


def test_read_file_returns_content(sample_repo):
    reader = RepositoryReader(str(sample_repo))
    content = reader.read_file("src/auth.py")
    assert "validate_token" in content


def test_read_file_returns_none_for_missing_file(sample_repo):
    reader = RepositoryReader(str(sample_repo))
    assert reader.read_file("src/does_not_exist.py") is None


def test_read_file_blocks_path_traversal(sample_repo):
    reader = RepositoryReader(str(sample_repo))
    assert reader.read_file("../../etc/passwd") is None


def test_get_existing_tests_finds_matching_test_file(sample_repo):
    reader = RepositoryReader(str(sample_repo))
    tests = reader.get_existing_tests("src/auth.py")
    assert any("test_auth.py" in t for t in tests)


def test_get_existing_tests_returns_empty_when_no_test_exists(sample_repo):
    reader = RepositoryReader(str(sample_repo))
    tests = reader.get_existing_tests("src/unrelated.py")
    assert tests == []


def test_search_repository_finds_matching_line(sample_repo):
    reader = RepositoryReader(str(sample_repo))
    matches = reader.search_repository("validate_token")
    assert any("auth.py" in m for m in matches)


def test_search_repository_respects_max_results(sample_repo):
    for i in range(20):
        (sample_repo / f"gen_{i}.py").write_text("needle = 1\n")
    reader = RepositoryReader(str(sample_repo))
    matches = reader.search_repository("needle", max_results=5)
    assert len(matches) <= 5


def test_inspect_git_history_returns_empty_when_not_a_git_repo(sample_repo):
    reader = RepositoryReader(str(sample_repo))
    history = reader.inspect_git_history("src/auth.py")
    assert history == []


def test_inspect_git_history_returns_commits_for_real_repo(sample_repo):
    subprocess.run(["git", "init", "-q"], cwd=sample_repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=sample_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=sample_repo, check=True)
    subprocess.run(["git", "add", "."], cwd=sample_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=sample_repo, check=True)

    reader = RepositoryReader(str(sample_repo))
    history = reader.inspect_git_history("src/auth.py")
    assert len(history) == 1
    assert "initial commit" in history[0]
