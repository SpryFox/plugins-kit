"""openrouter-kit CLI -- inspect, set, and validate the OpenRouter API key.

Subcommands:

    status      Resolve the key and validate it against /auth/key. Prints
                label, usage, limit, free-tier flag, and rate limit.
    set-key     Prompt for a new key (via getpass), validate it before
                writing, and store it in the user-scoped .env file. Pass
                --no-validate to skip the network round-trip.
    which       Print the resolved key's source path (or "missing").

Stdlib-only -- no third-party packages required.
"""

import argparse
import getpass
import json
import sys
from pathlib import Path

# Make the bundled lib/ importable when invoked directly.
_HERE = Path(__file__).resolve().parent
_LIB_DIR = _HERE.parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from openrouter_kit.account import AccountCheckError, check_account  # noqa: E402
from openrouter_kit.api_key import get_api_key  # noqa: E402
from openrouter_kit.constants import API_KEY_ENV, USER_ENV_FILE  # noqa: E402
from openrouter_kit.env_file import read_env_file, write_env_file  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openrouter-kit",
        description="Manage the OpenRouter API key for plugins-kit consumers.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Validate the resolved key and print account info.")

    p_set = sub.add_parser("set-key", help="Store a new API key in the user .env file.")
    p_set.add_argument(
        "--key",
        help="Key value. Omit to prompt securely via getpass.",
    )
    p_set.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip the /auth/key validation round-trip.",
    )

    sub.add_parser("which", help="Print the source path of the resolved key.")

    args = parser.parse_args(argv)

    if args.cmd == "status":
        return _cmd_status()
    if args.cmd == "set-key":
        return _cmd_set_key(args.key, validate=not args.no_validate)
    if args.cmd == "which":
        return _cmd_which()
    parser.error(f"unknown command: {args.cmd}")
    return 2


def _cmd_status() -> int:
    lookup = get_api_key()
    if lookup.key is None:
        print("No OpenRouter API key found.")
        print("Set one with `openrouter-kit set-key`.")
        return 1

    print(f"Source: {lookup.source}", end="")
    if lookup.source_path is not None:
        print(f" ({lookup.source_path})")
    else:
        print()

    try:
        status = check_account(lookup.key)
    except AccountCheckError as e:
        print(f"Validation failed: {e}", file=sys.stderr)
        return 2

    if not status.ok:
        print(f"Status: REJECTED ({status.failure_reason})")
        if status.failure_reason == "auth":
            print("The key was rejected (HTTP 401). Generate a new one at https://openrouter.ai/keys.")
        elif status.failure_reason == "no_credit":
            print("Account out of credit (HTTP 402). Add credit at https://openrouter.ai/credits.")
        return 1

    print("Status: OK")
    print(f"Label: {status.label or '<unlabeled>'}")
    if status.usage is not None:
        print(f"Usage: {status.usage}")
    if status.limit is not None:
        print(f"Limit: {status.limit}")
    if status.is_free_tier is not None:
        print(f"Free tier: {status.is_free_tier}")
    if status.rate_limit:
        print(f"Rate limit: {json.dumps(status.rate_limit)}")
    return 0


def _cmd_set_key(provided: str | None, *, validate: bool) -> int:
    key = provided
    if not key:
        try:
            key = getpass.getpass("OpenRouter API key (input hidden): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            return 130

    if not key:
        print("Empty key, nothing written.", file=sys.stderr)
        return 1

    if validate:
        try:
            status = check_account(key)
        except AccountCheckError as e:
            print(f"Could not validate key: {e}", file=sys.stderr)
            print("Pass --no-validate to write the key without checking it.", file=sys.stderr)
            return 2
        if not status.ok:
            print(f"Validation failed: {status.failure_reason}", file=sys.stderr)
            return 1

    # Preserve any existing keys in the file (today there's only one, but be
    # defensive in case future versions add more fields).
    existing = read_env_file(USER_ENV_FILE)
    existing[API_KEY_ENV] = key
    write_env_file(USER_ENV_FILE, existing)
    print(f"Wrote {API_KEY_ENV} to {USER_ENV_FILE}")
    return 0


def _cmd_which() -> int:
    lookup = get_api_key()
    if lookup.key is None:
        print("missing")
        return 1
    if lookup.source_path is not None:
        print(f"{lookup.source}: {lookup.source_path}")
    else:
        print(f"{lookup.source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
