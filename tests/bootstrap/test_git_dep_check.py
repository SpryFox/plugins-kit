"""Tests for git_dep_check.py — git dependency validation."""

import os
import subprocess

import pytest

from bootstrap_lib.git_dep_check import GitDepCheckResult, check_git_dep, _extract_repo_name


class TestExtractRepoName:
    def test_https_url(self):
        assert _extract_repo_name("https://github.com/octocat/Hello-World") == "Hello-World"

    def test_url_with_git_suffix(self):
        assert _extract_repo_name("https://github.com/octocat/Hello-World.git") == "Hello-World"

    def test_trailing_slash(self):
        assert _extract_repo_name("https://github.com/octocat/Hello-World/") == "Hello-World"


class TestCheckGitDep:
    def test_missing_directory(self, tmp_path):
        """Returns failure when clone directory doesn't exist."""
        result = check_git_dep(
            str(tmp_path), "https://github.com/octocat/Hello-World", "master",
        )

        assert not result.passed
        assert "not cloned" in result.message
        assert result.repo_name == "Hello-World"
        assert "git clone" in result.remediation_cmd

    def test_directory_not_git_repo(self, tmp_path):
        """Returns failure when directory exists but is not a git repo."""
        target = tmp_path / "github" / "Hello-World"
        target.mkdir(parents=True)

        result = check_git_dep(
            str(tmp_path), "https://github.com/octocat/Hello-World", "master",
        )

        assert not result.passed
        assert "not a git repo" in result.message

    def test_correct_clone(self, tmp_path):
        """Passes when directory is a git repo on the correct branch."""
        target = tmp_path / "github" / "my-repo"
        target.mkdir(parents=True)

        # Init a real git repo on the expected branch
        subprocess.run(["git", "init", str(target)], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(target), "checkout", "-b", "main"],
            capture_output=True, check=True,
        )
        # Need at least one commit for branch to exist
        subprocess.run(
            ["git", "-C", str(target), "commit", "--allow-empty", "-m", "init"],
            capture_output=True, check=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
                 "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com"},
        )

        result = check_git_dep(
            str(tmp_path), "https://github.com/example/my-repo", "main",
        )

        assert result.passed
        assert "cloned on main" in result.message
        assert result.remediation_cmd is None

    def test_wrong_branch(self, tmp_path):
        """Returns failure when repo is on wrong branch."""
        target = tmp_path / "github" / "my-repo"
        target.mkdir(parents=True)

        env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
               "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com"}
        subprocess.run(["git", "init", str(target)], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(target), "checkout", "-b", "develop"],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "commit", "--allow-empty", "-m", "init"],
            capture_output=True, check=True, env=env,
        )

        result = check_git_dep(
            str(tmp_path), "https://github.com/example/my-repo", "main",
        )

        assert not result.passed
        assert "develop" in result.message
        assert "expected main" in result.message
        assert "checkout main" in result.remediation_cmd

    def test_sparse_checkout_remediation(self, tmp_path):
        """Remediation includes sparse-checkout when sparse_paths specified."""
        result = check_git_dep(
            str(tmp_path), "https://github.com/octocat/Hello-World", "master",
            sparse_paths=["README", "docs"],
        )

        assert not result.passed
        assert "sparse-checkout" in result.remediation_cmd
        assert "README" in result.remediation_cmd
        assert "docs" in result.remediation_cmd

    def test_target_path_uses_github_subdir(self, tmp_path):
        """Clone target is always <data_dir>/github/<repo_name>/."""
        result = check_git_dep(
            str(tmp_path), "https://github.com/octocat/Hello-World", "master",
        )

        expected = os.path.join(str(tmp_path), "github", "Hello-World")
        assert result.target_path == expected
