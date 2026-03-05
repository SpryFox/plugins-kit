#!/usr/bin/env python3
"""Run a code review and output results to stdout.

Usage:
  python run-review.py <CL> [--agent NAME] [--diff-file FILE] [--dry-run] [--json]

Environment:
  PLUGIN_DATA_DIR — plugin data directory (default: ~/.claude/plugins/data/local-review-kit)

Outputs ReviewResult as YAML (default) or JSON to stdout.
Diagnostic messages go to stderr.
"""

import argparse
import json
import os
import sys
from pathlib import Path


# --- Minimal YAML reader (stdlib only, matches setup.py) ---

def read_config(config_path):
    """Read simple key: \"value\" YAML into a dict."""
    result = {}
    if not os.path.isfile(config_path):
        return result
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            result[key] = value
    return result


def _resolve_data_dir() -> Path:
    """Resolve the plugin data directory."""
    env = os.environ.get("PLUGIN_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return Path("~/.claude/plugins/data/local-review-kit").expanduser().resolve()


def _die(msg: str) -> None:
    """Print error to stderr and exit."""
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Run a code review and output results to stdout"
    )
    parser.add_argument(
        "changelist",
        help="Changelist number to review"
    )
    parser.add_argument(
        "--agent",
        help="Agent name (default: DEFAULT_AGENT from config.yaml)"
    )
    parser.add_argument(
        "--diff-file",
        type=Path,
        help="Read diff from file instead of p4 describe"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print assembled prompts without calling LLM"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of YAML"
    )
    args = parser.parse_args()

    # 1. Resolve data dir and read config
    data_dir = _resolve_data_dir()
    config_path = data_dir / "config.yaml"
    if not config_path.is_file():
        _die(f"Config not found: {config_path}\nRun plugin setup first.")

    config = read_config(str(config_path))

    # 2. Resolve agent name
    agent_name = args.agent or config.get("DEFAULT_AGENT", "")
    if not agent_name:
        _die("No agent specified and no DEFAULT_AGENT in config.yaml")

    # 3. Set env vars from config (replaces load_env)
    env_mapping = {
        "OPENAI_API_KEY": "OPENAI_API_KEY",
        "OPENROUTER_API_KEY": "OPENROUTER_API_KEY",
        "P4PORT": "P4PORT",
        "P4USER": "P4USER",
    }
    for config_key, env_key in env_mapping.items():
        value = config.get(config_key, "")
        if value and value.lower() != "none":
            os.environ.setdefault(env_key, value)

    # 4. Set CODE_REVIEW_ROOT before importing code_review
    code_review_root = data_dir / "github" / "code-review-research"
    if not code_review_root.is_dir():
        _die(
            f"code-review-research not found at {code_review_root}\n"
            "Run plugin bootstrap (fetch-git-deps) first."
        )
    os.environ["CODE_REVIEW_ROOT"] = str(code_review_root)

    # 5. Import code_review modules (after CODE_REVIEW_ROOT is set)
    try:
        from code_review.config import load_agent_config
        from code_review.review_engine import build_prompts, run_review
    except ImportError as e:
        _die(f"Failed to import code_review: {e}\nIs the venv activated?")

    # 6. Load agent config
    try:
        agent_config = load_agent_config(agent_name)
    except FileNotFoundError as e:
        _die(str(e))
    except ValueError as e:
        _die(f"Invalid agent config: {e}")

    # 7. Get diff text
    if args.diff_file:
        if not args.diff_file.is_file():
            _die(f"Diff file not found: {args.diff_file}")
        diff_text = args.diff_file.read_text()
    else:
        try:
            from code_review.p4 import get_changelist_diff
            diff_text = get_changelist_diff(args.changelist)
        except ValueError as e:
            _die(str(e))

    # 8. Dry-run: print prompts to stderr and exit
    if args.dry_run:
        prompts = build_prompts(args.changelist, agent_config, diff_text)
        print("=== SYSTEM PROMPT ===", file=sys.stderr)
        print(prompts.system_prompt, file=sys.stderr)
        print("\n=== USER PROMPT ===", file=sys.stderr)
        print(prompts.user_prompt, file=sys.stderr)
        if prompts.overflow_files:
            print(f"\n=== OVERFLOW FILES ({len(prompts.overflow_files)}) ===", file=sys.stderr)
            for f in prompts.overflow_files:
                print(f"  {f}", file=sys.stderr)
        sys.exit(0)

    # 9. Run review
    print(f"Running review: CL {args.changelist} with {agent_name}...", file=sys.stderr)
    try:
        result = run_review(args.changelist, agent_config, diff_text)
    except (ValueError, RuntimeError) as e:
        _die(f"Review failed: {e}")

    # 10. Serialize to stdout (no disk writes)
    # Exclude raw_response from output (large, not needed for display)
    data = result.model_dump(exclude={"raw_response"})

    if args.json_output:
        json.dump(data, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        try:
            import yaml
            yaml.dump(data, sys.stdout, default_flow_style=False, sort_keys=False)
        except ImportError:
            # Fallback to JSON if PyYAML not available
            print("Warning: PyYAML not available, falling back to JSON", file=sys.stderr)
            json.dump(data, sys.stdout, indent=2, default=str)
            sys.stdout.write("\n")


if __name__ == "__main__":
    main()
