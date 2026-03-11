"""Tests that git network operations suppress interactive credential prompts.

GIT_TERMINAL_PROMPT=0 must be set on all git subprocess calls that contact
remotes (clone, pull). Without it, git falls back to prompting for username/
password on HTTPS URLs, blocking bootstrap in non-interactive sessions.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from bootstrap_lib.git_dep_check import clone_git_dep, pull_git_dep
from bootstrap_lib.marketplace_lifecycle import _run_claude


def _all_envs(mock_run: MagicMock) -> list[dict]:
    """Return the env dict from every subprocess.run call."""
    envs = []
    for c in mock_run.call_args_list:
        env = c.kwargs.get("env")
        envs.append(env)
    return envs


class TestCloneGitDepNoPrompt:
    def test_clone_sets_git_terminal_prompt(self, tmp_path: pytest.fixture) -> None:
        """clone_git_dep must pass GIT_TERMINAL_PROMPT=0 to every git call."""
        with patch("bootstrap_lib.git_dep_check.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            clone_git_dep(
                "https://github.com/example/repo.git",
                "main",
                str(tmp_path / "repo"),
            )
            for env in _all_envs(mock_run):
                assert env is not None, "subprocess.run called without env= argument"
                assert env.get("GIT_TERMINAL_PROMPT") == "0", (
                    "GIT_TERMINAL_PROMPT=0 missing from git clone subprocess call"
                )

    def test_sparse_clone_sets_git_terminal_prompt(self, tmp_path: pytest.fixture) -> None:
        """Sparse clone path also passes GIT_TERMINAL_PROMPT=0."""
        with patch("bootstrap_lib.git_dep_check.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            clone_git_dep(
                "https://github.com/example/repo.git",
                "main",
                str(tmp_path / "repo"),
                sparse_paths=["docs/"],
            )
            for env in _all_envs(mock_run):
                assert env is not None
                assert env.get("GIT_TERMINAL_PROMPT") == "0"


class TestPullGitDepNoPrompt:
    def test_pull_sets_git_terminal_prompt(self, tmp_path: pytest.fixture) -> None:
        """pull_git_dep must pass GIT_TERMINAL_PROMPT=0 to git pull."""
        with patch("bootstrap_lib.git_dep_check.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            pull_git_dep(str(tmp_path))
            for env in _all_envs(mock_run):
                assert env is not None, "subprocess.run called without env= argument"
                assert env.get("GIT_TERMINAL_PROMPT") == "0", (
                    "GIT_TERMINAL_PROMPT=0 missing from git pull subprocess call"
                )


class TestRunClaudeNoPrompt:
    def test_run_claude_sets_git_terminal_prompt(self) -> None:
        """_run_claude must pass GIT_TERMINAL_PROMPT=0 so claude's git ops don't prompt."""
        with patch("bootstrap_lib.marketplace_lifecycle.shutil.which", return_value="/usr/bin/claude"):
            with patch("bootstrap_lib.marketplace_lifecycle.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                _run_claude(["plugin", "marketplace", "update"])
                env = mock_run.call_args.kwargs.get("env")
                assert env is not None, "subprocess.run called without env= argument"
                assert env.get("GIT_TERMINAL_PROMPT") == "0", (
                    "GIT_TERMINAL_PROMPT=0 missing from _run_claude subprocess call"
                )
