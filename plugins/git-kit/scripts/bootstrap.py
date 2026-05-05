"""git-kit bootstrap script.

Verifies the GitHub CLI is authenticated. If the project's bootstrap.json
declares a required organization under `git_kit.required_organization`,
verifies the authenticated user is a member; if `git_kit.access_remediation`
is also set, that text is surfaced as the per-project remediation hint
(e.g. "ask @dmo for access to the SpryFox repository"). Org membership is
only checked when the user is authenticated -- otherwise the auth failure
takes priority.

Failures are registered as fix-all entries so the user is prompted to
remediate (typically by running `! gh auth login --web` in their terminal).
"""

import json
import shutil
import subprocess
from pathlib import Path


GH_AUTH_LOGIN_HINT = "! gh auth login --hostname github.com --git-protocol https --web"


def bootstrap(ctx) -> None:
    gh = shutil.which("gh")
    if not gh:
        ctx.log("gh: not found on PATH after install phase, skipping auth check")
        return

    auth_ok, auth_user = _check_auth(gh)
    if not auth_ok:
        ctx.log("github auth: not logged in")
        ctx.add_failure(
            "user_config",
            field="github_auth",
            user_msg="Not logged in to GitHub. Authenticate via the GitHub CLI.",
            agent_msg=(
                "GitHub CLI is not authenticated. Tell the user to authenticate "
                f"by typing `{GH_AUTH_LOGIN_HINT}` (with the leading `!`) at the "
                "Claude Code prompt -- the `!` runs it in their terminal so the "
                "browser flow works. After they confirm auth succeeded, type 'fixed'."
            ),
        )
        return

    ctx.log(f"github auth: ok (logged in as {auth_user})" if auth_user else "github auth: ok")

    required_org, access_remediation = _project_org_config(ctx.project_dir)
    if not required_org:
        return

    member, orgs = _check_org_membership(gh, required_org)
    if member:
        ctx.log(f"github org: ok (member of {required_org})")
        return

    org_list = ", ".join(orgs) if orgs else "(none visible)"
    ctx.log(f"github org: not a member of {required_org} (visible orgs: {org_list})")

    user_msg = (
        f"Your GitHub account is not a member of the required organization '{required_org}'."
    )
    if access_remediation:
        user_msg += f" To remediate: {access_remediation}."
    agent_msg_parts = [
        f"GitHub authenticated as `{auth_user or 'unknown'}` is not a member of the required "
        f"organization `{required_org}` (visible orgs: {org_list})."
    ]
    if access_remediation:
        agent_msg_parts.append(
            f"Tell the user verbatim: \"{access_remediation}\". "
            "Once access is granted they may need to run "
            "`gh auth refresh -h github.com -s read:org` so the org becomes visible to the CLI, "
            "then type 'fixed'."
        )
    else:
        agent_msg_parts.append(
            "Tell the user this needs to be resolved by an org admin (granting access), "
            "after which they may need to re-run `gh auth refresh -h github.com -s read:org` "
            "so the org becomes visible to the CLI. Then type 'fixed'."
        )

    ctx.add_failure(
        "config",
        field="github_org",
        user_msg=user_msg,
        agent_msg=" ".join(agent_msg_parts),
    )


def _check_auth(gh: str):
    try:
        proc = subprocess.run(
            [gh, "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return False, None
    if proc.returncode != 0:
        return False, None

    user = None
    for line in (proc.stderr + proc.stdout).splitlines():
        line = line.strip()
        if "account " in line.lower() and "(" in line:
            try:
                user = line.split("account", 1)[1].strip().split(" ")[0]
            except IndexError:
                pass
            break
        if "Logged in to" in line and " as " in line:
            try:
                user = line.split(" as ", 1)[1].split(" ")[0]
            except IndexError:
                pass
            break
    return True, user


def _check_org_membership(gh: str, required_org: str):
    try:
        proc = subprocess.run(
            [gh, "api", "user/orgs", "--jq", ".[].login"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return False, []
    if proc.returncode != 0:
        return False, []
    orgs = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    target = required_org.lower()
    member = any(o.lower() == target for o in orgs)
    return member, orgs


def _project_org_config(project_dir):
    """Returns (required_organization, access_remediation) from project bootstrap.json."""
    if not project_dir:
        return None, None
    candidate = Path(project_dir) / ".claude" / "bootstrap.json"
    if not candidate.is_file():
        return None, None
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    section = data.get("git_kit") or {}
    org = section.get("required_organization")
    org = org.strip() if isinstance(org, str) and org.strip() else None
    remediation = section.get("access_remediation")
    remediation = remediation.strip() if isinstance(remediation, str) and remediation.strip() else None
    return org, remediation
