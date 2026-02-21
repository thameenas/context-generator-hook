"""Tests for git operations module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from git import Repo

from context_hook.git import (
    get_diff,
    get_diff_file_chunks,
    get_commit_message,
    get_file_tree,
    get_file_contents,
    get_prioritized_file_list,
)


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repo with some files and commits."""
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    # Create initial files
    (tmp_path / "README.md").write_text("# Test Project\nA test project.")
    (tmp_path / "main.py").write_text("def main():\n    print('hello')\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.py").write_text("def helper():\n    pass\n")

    repo.index.add(["README.md", "main.py", "pyproject.toml", "src/utils.py"])
    repo.index.commit("Initial commit")

    # Second commit with a change
    (tmp_path / "main.py").write_text("def main():\n    print('hello world')\n")
    (tmp_path / "src" / "new_module.py").write_text("class Foo:\n    pass\n")
    repo.index.add(["main.py", "src/new_module.py"])
    repo.index.commit("Add new module and update main")

    return tmp_path, repo


class TestGetDiff:
    def test_returns_diff_string(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            diff = get_diff()
            assert isinstance(diff, str)
            assert len(diff) > 0

    def test_diff_contains_changes(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            diff = get_diff()
            assert "hello world" in diff

    def test_first_commit_diff(self, tmp_path):
        """Test diff when there's only one commit (no parent)."""
        repo = Repo.init(tmp_path)
        repo.config_writer().set_value("user", "name", "Test").release()
        repo.config_writer().set_value("user", "email", "test@test.com").release()
        (tmp_path / "file.txt").write_text("content")
        repo.index.add(["file.txt"])
        repo.index.commit("First commit")

        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = repo
            diff = get_diff()
            assert "content" in diff


class TestGetDiffFileChunks:
    def test_returns_list_of_chunks(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            chunks = get_diff_file_chunks()
            assert isinstance(chunks, list)
            assert len(chunks) > 0

    def test_chunk_structure(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            chunks = get_diff_file_chunks()
            for chunk in chunks:
                assert "file" in chunk
                assert "diff" in chunk
                assert "status" in chunk
                assert chunk["status"] in ("added", "modified", "deleted", "renamed")

    def test_identifies_new_and_modified_files(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            chunks = get_diff_file_chunks()
            statuses = {c["file"]: c["status"] for c in chunks}
            assert statuses.get("src/new_module.py") == "added"
            assert statuses.get("main.py") == "modified"


class TestGetCommitMessage:
    def test_returns_commit_message(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            msg = get_commit_message()
            assert msg == "Add new module and update main"


class TestGetFileTree:
    def test_returns_sorted_file_list(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            tree = get_file_tree()
            assert isinstance(tree, list)
            assert tree == sorted(tree)

    def test_excludes_git_directory(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            tree = get_file_tree()
            assert not any(".git" in f for f in tree)

    def test_includes_tracked_files(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            tree = get_file_tree()
            assert "README.md" in tree
            assert "main.py" in tree
            assert "src/utils.py" in tree


class TestGetFileContents:
    def test_reads_files_within_budget(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            contents = get_file_contents(["README.md", "main.py"], max_total_chars=10000)
            assert "README.md" in contents
            assert "main.py" in contents

    def test_respects_char_budget(self, temp_repo):
        repo_path, _ = temp_repo
        with patch("context_hook.git.get_repo") as mock:
            mock.return_value = Repo(repo_path)
            # Very small budget — should only read first file
            contents = get_file_contents(
                ["README.md", "main.py"],
                max_total_chars=30,
            )
            total_chars = sum(len(v) for v in contents.values())
            assert total_chars <= 50  # 30 + truncation text


class TestGetPrioritizedFileList:
    def test_priority_files_first(self):
        files = ["src/utils.py", "main.py", "pyproject.toml", "README.md"]
        prioritized = get_prioritized_file_list(files)
        # README.md and pyproject.toml should be before src/utils.py
        readme_idx = prioritized.index("README.md")
        pyproject_idx = prioritized.index("pyproject.toml")
        utils_idx = prioritized.index("src/utils.py")
        assert readme_idx < utils_idx
        assert pyproject_idx < utils_idx

    def test_shallower_files_first(self):
        files = ["a/b/c/deep.py", "shallow.py"]
        prioritized = get_prioritized_file_list(files)
        assert prioritized.index("shallow.py") < prioritized.index("a/b/c/deep.py")
