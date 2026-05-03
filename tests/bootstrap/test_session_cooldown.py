"""Tests for the per-project cooldown logic in session-bootstrap.sh and the
bootstrap-reset-cooldown helper script.

These pin the regression: Bug 2 in the statusline-not-installed-per-project
report. The cooldown used to live in a single file (`last_run_epoch`) shared
across every project, so launching claude in project B within 5 minutes of
project A would silently skip B's bootstrap. Cooldown must now be keyed by
project_dir, the throttle bumped to 3600s, and skips logged with a reset hint.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_BOOTSTRAP = REPO_ROOT / "plugins" / "bootstrap" / "hooks" / "sessionstart" / "session-bootstrap.sh"
RESET_SCRIPT = REPO_ROOT / "plugins" / "bootstrap" / "scripts" / "bootstrap-reset-cooldown.sh"


def _find_bash() -> str | None:
    """Find a POSIX-compatible bash. On Windows, prefer Git Bash over WSL bash
    (which lives at C:\\Windows\\System32\\bash.exe and can't access this VHDX)."""
    candidates = []
    if os.name == "nt":
        candidates.extend([
            r"C:\Program Files\Git\usr\bin\bash.exe",
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\usr\bin\bash.exe",
        ])
    found = shutil.which("bash")
    if found:
        candidates.append(found)
    for c in candidates:
        if c and Path(c).exists() and "WindowsApps" not in c and "System32" not in c:
            return c
    return None


BASH = _find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available on this platform")


class TestCooldownContract:
    """Static checks on session-bootstrap.sh — cheap and platform-independent."""

    def test_cooldown_is_per_project(self) -> None:
        text = SESSION_BOOTSTRAP.read_text()
        assert "_COOLDOWN_DIR=" in text, "cooldown dir variable missing"
        assert "last_run_epoch.$_PROJECT_KEY" in text, (
            "cooldown file must be keyed by project hash; "
            "shared global file regresses bug-report Bug 2"
        )

    def test_cooldown_window_is_one_hour(self) -> None:
        text = SESSION_BOOTSTRAP.read_text()
        assert "_COOLDOWN_SECS=3600" in text, (
            "cooldown bumped to 3600s now that it's per-project; "
            "reset via bootstrap-reset-cooldown when needed"
        )

    def test_skip_is_logged(self) -> None:
        text = SESSION_BOOTSTRAP.read_text()
        assert "cooldown: skipped" in text, (
            "cooldown skips must emit a log line so users can distinguish "
            "throttled-skip from clean-pass"
        )
        assert "bootstrap-reset-cooldown" in text, "log line should mention the reset tool"

    def test_reset_script_installed_to_local_bin(self) -> None:
        text = SESSION_BOOTSTRAP.read_text()
        assert "_RESET_SRC=" in text, "session-bootstrap should install the reset helper"
        assert "bootstrap-reset-cooldown" in text


@needs_bash
class TestResetScript:
    """Behavioral tests for bootstrap-reset-cooldown.sh."""

    def _run(self, *args: str, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        return subprocess.run(
            [BASH, str(RESET_SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def _seed_cooldown(self, fake_home: Path, marketplace: str, project_dir: str) -> Path:
        """Create a stand-in cooldown file by replicating the script's hash."""
        # Match session-bootstrap.sh / reset script hashing: sha1 of the path string.
        out = subprocess.run(
            [BASH, "-c", f'printf "%s" "{project_dir}" | sha1sum | awk \'{{print $1}}\''],
            capture_output=True, text=True,
        )
        key = out.stdout.strip()
        assert key, f"sha1 hashing failed: {out.stderr}"
        cooldown_dir = fake_home / ".claude" / "plugins" / "data" / marketplace / "bootstrap" / "cooldowns"
        cooldown_dir.mkdir(parents=True, exist_ok=True)
        f = cooldown_dir / f"last_run_epoch.{key}"
        f.write_text(str(int(time.time())))
        return f

    def test_default_resets_current_project(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        proj = tmp_path / "myproj"
        proj.mkdir()
        # Resolve the project path the way bash will see it after `cd` (e.g.
        # /c/Users/... on Git Bash for Windows), and seed the cooldown under
        # the hash of that string so default mode locates it.
        resolved = subprocess.run(
            [BASH, "-c", f'cd "{proj}" && printf %s "$PWD"'],
            capture_output=True, text=True,
        )
        bash_pwd = resolved.stdout
        assert bash_pwd, f"failed to resolve bash PWD: {resolved.stderr}"
        cooldown_file = self._seed_cooldown(fake_home, "plugins-kit", bash_pwd)
        assert cooldown_file.exists()

        result = subprocess.run(
            [BASH, "-c", f'cd "{proj}" && HOME="{fake_home}" "{BASH}" "{RESET_SCRIPT}"'],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert not cooldown_file.exists(), "default mode should reset CWD's cooldown"
        assert "reset cooldown" in result.stdout

    def test_explicit_project(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        proj = tmp_path / "explicit"
        proj.mkdir()
        cooldown_file = self._seed_cooldown(fake_home, "plugins-kit", str(proj))

        result = self._run("--project", str(proj), env_overrides={"HOME": str(fake_home)})
        assert result.returncode == 0, result.stderr
        assert not cooldown_file.exists()

    def test_all_resets_every_project(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        proj_a = tmp_path / "a"
        proj_b = tmp_path / "b"
        proj_a.mkdir()
        proj_b.mkdir()
        f_a = self._seed_cooldown(fake_home, "plugins-kit", str(proj_a))
        f_b = self._seed_cooldown(fake_home, "plugins-kit", str(proj_b))

        result = self._run("--all", env_overrides={"HOME": str(fake_home)})
        assert result.returncode == 0, result.stderr
        assert not f_a.exists()
        assert not f_b.exists()

    def test_status_reports_without_writes(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        proj = tmp_path / "p"
        proj.mkdir()
        f = self._seed_cooldown(fake_home, "plugins-kit", str(proj))

        result = self._run("--status", env_overrides={"HOME": str(fake_home)})
        assert result.returncode == 0, result.stderr
        assert f.exists(), "--status must not delete cooldown files"
        assert "age=" in result.stdout

    def test_clear_alerts(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        plugin_data = fake_home / ".claude" / "plugins" / "data" / "plugins-kit" / "bootstrap"
        plugin_data.mkdir(parents=True)
        alert = plugin_data / "bootstrap_alert.json"
        pending = plugin_data / "bootstrap_display.pending"
        alert.write_text("{}")
        pending.write_text("{}")

        result = self._run("--all", "--clear-alerts", env_overrides={"HOME": str(fake_home)})
        assert result.returncode == 0, result.stderr
        assert not alert.exists()
        assert not pending.exists()

    def test_unknown_arg_errors(self) -> None:
        result = self._run("--bogus")
        assert result.returncode == 2
        assert "unknown argument" in result.stderr
