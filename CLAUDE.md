# CLAUDE.md

## Project Overview

**plugins-kit** is the **development repository** (source of truth) for the plugins-kit Claude Code marketplace. It contains the source code for all plugins in the marketplace. Currently ships (published): **awesome-kit** (cross-domain skills: shared comms framework, update-documentation, /plugin-ecosystem, /html-pdf), **bootstrap** (dependency management), **cache-kit** (cache-usage reporting from transcripts), **claude-ui-kit** (status line + /statusline), **git-kit** (Git/GitHub multi-agent code review + gh bootstrap), **openrouter-kit** (OpenRouter key management + shared model registry), **p4-kit** (Perforce multi-agent code review), **prototypes** (experimental skills awaiting graduation), **skills-kit** (skill-authoring framework), **test-plugin** (bootstrap exerciser), and **unreal-kit** (Unreal Engine Python API automation). Dev-only (not published, `published: false`): **agent-glue**, **workflow-kit**.

This repo is a **Claude Code plugin marketplace** — it extends Claude Code with skills, commands, and hooks via the `.claude-plugin/marketplace.json` manifest. Plugins are loaded either via `--plugin-dir` (local development) or `enabledPlugins` in settings (production installs from the remote repo).

## Architecture

```
plugins-kit/                          # Marketplace root
  .claude-plugin/marketplace.json     # Marketplace manifest (lists all plugins)
  plugins/
    bootstrap/                        # Bootstrap plugin (always enabled)
      .claude-plugin/plugin.json      # Plugin manifest
      bootstrap.json                  # Bootstrap plugin's own manifest
      engine/                         # Bootstrap engine + config
      bootstrap_lib/                  # Shared libraries (cache, tool_check, etc.) — installable Python package
      hooks/sessionstart/             # SessionStart hook (bash wrapper)
      defaults/                       # Default config files
    test-plugin/                      # Test plugin (exercises bootstrap system)
      .claude-plugin/plugin.json      # Plugin manifest
      bootstrap.json                  # Test plugin's bootstrap manifest
      scripts/                        # Config setup
    p4-kit/                           # P4 multi-agent code review plugin (Claude subagents)
      .claude-plugin/plugin.json      # Plugin manifest
      bootstrap.json                  # Bootstrap manifest (tools)
      scripts/prepare_review.py       # Diff + CLAUDE.md gathering (stdlib-only, called by skill)
      skills/p4-code-review/          # Multi-agent review skill (3 reviewers + per-issue validators)
    unreal-kit/                       # The UE plugin
      .claude-plugin/plugin.json      # Plugin manifest
      lib/                            # Shared Python libraries (synced to data dir by bootstrap)
      skills/
        ue-python-api/                # The main skill
          SKILL.md                    # Skill definition (loaded by Claude Code)
          bin/                        # Entry points (runner + setup)
          scripts/                    # Utility scripts
          stubs/                      # UE Python API stubs (generated, gitignored)
          references/                 # Detailed docs loaded conditionally by SKILL.md
```

### Key Files

| File | Purpose |
|------|---------|
| `plugins/bootstrap/engine/bootstrap_engine.py` | Main engine — processes manifests, runs checks, emits hook JSON |
| `plugins/bootstrap/bootstrap_lib/cache.py` | Content-hash caching (compute, check, write) |
| `plugins/bootstrap/bootstrap_lib/tool_check.py` | System tool availability checks |
| `plugins/bootstrap/bootstrap_lib/platform_detect.py` | OS detection |
| `plugins/bootstrap/bootstrap_lib/log.py` | File-based bootstrap logging |
| `plugins/bootstrap/bootstrap_lib/venv_check.py` | Python venv validation |
| `plugins/bootstrap/bootstrap_lib/git_dep_check.py` | Git dependency validation |
| `plugins/bootstrap/bootstrap_lib/plugin_resolve.py` | Plugin registry resolution |
| `plugins/bootstrap/bootstrap_lib/path_check.py` | PATH entry validation |
| `plugins/bootstrap/bootstrap_lib/manifest_merge.py` | Deep-merge for layered bootstrap.json files |
| `plugins/bootstrap/engine/config.py` | Config loading, migration, persistence |
| `plugins/bootstrap/hooks/sessionstart/session-bootstrap.sh` | SessionStart hook (bash wrapper for engine) |
| `plugins/bootstrap/bootstrap.json` | Bootstrap plugin's own manifest |
| `plugins/bootstrap/skills/bootstrap/references/engine-internals.md` | Bootstrap engine internals |
| `docs/planning/bootstrap/MILESTONES.md` | Development milestones and progress |
| `plugins/test-plugin/bootstrap.json` | Test plugin's bootstrap manifest (includes config section) |
| `tests/bootstrap/` | All bootstrap tests (mirrors bootstrap_lib/ structure) |

### Key Design Decisions

- **Bootstrapping**: Two-layer system — session bootstrap (bash SessionStart hook, manifest-driven) ensures system tools, venv, and git deps; script bootstrap (Python, runs inside UE Editor) handles UE-side packages at runtime. See [engine-internals.md](plugins/bootstrap/skills/bootstrap/references/engine-internals.md) for engine details and [script-bootstrap.md](plugins/unreal-kit/skills/ue-python-api/references/script-bootstrap.md) for UE-side bootstrapping.
- **Config resolution order**: CLI args > per-project config (`<project_root>/.claude/unreal-kit.yaml`) > global config (`~/.claude/plugins/data/plugins-kit/unreal-kit/config.yaml`, legacy fallback) > skill config (`ue_runner_config.yaml`) > hardcoded defaults
- **Auto-detection execution**: `ue_runner.py` tries remote execution (UDP via upyrc) first, falls back to headless commandlet if editor isn't running

### Unreal Engine work

For UE Python automation (running scripts, the `ue_runner` host-side runner, in-editor patterns, sys.path conventions, dependency bootstrap), invoke the `ue-python-api` skill at `plugins/unreal-kit/skills/ue-python-api/SKILL.md`.

## Bootstrap (foundation for all plugins)

The **bootstrap** plugin is the dependency-management layer every other plugin in this marketplace rides on. Claude Code runs it via a SessionStart hook at the start of every session; bootstrap then reads each enabled plugin's `bootstrap.json` and ensures system tools, venvs, git deps, marketplaces, and per-user config are in the state the plugins need. **No bootstrap, no working plugins.** When a `bootstrap.json` changes (e.g. a new Python dependency, a new check), the next session that actually runs bootstrap will apply those checks and remediate.

**Healthy bootstrap is silent.** No SessionStart output does NOT mean bootstrap is broken; it means every check passed (or hit a cache). To verify a plugin's bootstrap actually ran, read its log at `~/.claude/plugins/data/<marketplace>/<plugin>/bootstrap.log`. If the log doesn't exist, bootstrap never reached that plugin -- most often because the per-project cooldown short-circuited the run (see below).

**Per-project cooldown.** After bootstrap finishes for a project, it writes a per-project timestamp at `~/.claude/plugins/data/plugins-kit/bootstrap/cooldowns/last_run_epoch.<sha1-of-cwd>`. Subsequent SessionStart hooks within the cooldown window are skipped entirely -- bootstrap does NOT re-check anything, no logs are written, no remediation runs. After a `bootstrap.json` change, after publishing a plugin update you want pulled in immediately, or any time bootstrap appears to be ignoring you, clear the cooldown:

```bash
bash plugins/bootstrap/scripts/bootstrap-reset-cooldown.sh             # current project (CWD)
bash plugins/bootstrap/scripts/bootstrap-reset-cooldown.sh --all       # every project
bash plugins/bootstrap/scripts/bootstrap-reset-cooldown.sh --status    # list cooldowns + ages, no writes
bash plugins/bootstrap/scripts/bootstrap-reset-cooldown.sh --clear-alerts  # also nuke pending alert/display files
```

The reset script's `--help` is the canonical doc; the usage block lives inline at `plugins/bootstrap/scripts/bootstrap-reset-cooldown.sh:2-18`.

**Two caches, do not confuse them.** The cooldown above short-circuits the entire bootstrap run for a project. Separately, the engine content-hashes individual *checks* via `bootstrap_cache.sha256` in the same data dir -- that cache skips one specific check when its input manifest hasn't changed. The cooldown is the bigger hammer; clearing it is the right tool ~99% of the time. Don't reach for `bootstrap_cache.sha256` unless you've ruled out the cooldown.

For deeper material -- manifest schema, condition categories, fix-all flow, engine internals -- invoke `/bootstrap`.

## Development Workflow

**Automated tests required** — every new module or integration point must have corresponding tests in `tests/` before the work is considered complete. Test directories mirror the plugin structure (e.g. `tests/bootstrap/` for the bootstrap plugin). This standard was established with the bootstrap plugin's M1 test suite and applies to all subsequent development.

**Targeted test runs** — the full test suite is too slow for routine use. Always run only the specific test file(s) relevant to your changes:

```bash
# Run a specific test file
uv run --extra dev pytest tests/bootstrap/test_marketplace_lifecycle.py -v

# Run a specific test class
uv run --extra dev pytest tests/bootstrap/test_marketplace_lifecycle.py::TestCheckPluginScope -v
```

Only run the full suite (`uv run --extra dev pytest -v`) when explicitly asked or before a release.

**Interpreter: the repo is pinned to Python 3.12** via a repo-root `.python-version`, so bare `uv run` / `uv venv` select 3.12 everywhere — no `-p 3.12` needed. Nothing needs 3.14 (four plugins exclude it: `requires-python ">=3.12,!=3.14.*"`); it used to leak in only as uv's global default when no pin was present.

The two formerly-documented "pre-existing failure" clusters (the `tests/skills-kit/` collection errors and the bootstrap `engine`/`venv` `CalledProcessError`s) were **fixed**, not version quirks — both were test-only issues: skills-kit imported the pre-extraction `schemas`/`_shared` modules, and the bootstrap tests spawned WSL `bash` to `source` a Windows env file and didn't isolate `HOME`. The full suite is green; investigate any failure as a real regression.

**Local development** — use `--plugin-dir` to test plugins from the working copy:

```bash
claude --plugin-dir ~/Dev/plugins-kit/plugins/my-plugin
```

`--plugin-dir` loads the plugin directly from disk (no cache copy) and makes no persistent changes — it doesn't modify `installed_plugins.json`, the cache, or `known_marketplaces.json`. Ending the session reverts to the marketplace-installed version. Use `/reload-plugins` to pick up file changes within a session (hooks require a full restart).

**Publishing changes** — the plugin cache syncs from the remote repository's default branch, not the local working copy. Develop on the `dev` branch; merge to `master` only when releasing a version bump. This prevents silent divergence (fresh installs between releases getting HEAD code cached under the old version string).

**Definition.** "Publish" in this repo means **all three** of:

1. Bump the plugin version in `plugins/<name>/.claude-plugin/plugin.json` (the plugin's own manifest is the source of truth). Then regenerate the marketplace listing:
   ```bash
   python scripts/regen_marketplace.py
   ```
   `.claude-plugin/marketplace.json` is **derived data** — its `plugins[]` array is rebuilt from each plugin's `plugin.json`, filtered by the `"published"` field (missing = `true`; `false` = excluded from the marketplace). Do not hand-edit marketplace.json plugin entries; the pre-commit hook will reject drift.
2. Push the version-bumped commit to `origin/dev`.
3. Merge `dev` to `master` (via PR or fast-forward) and push to `origin/master`.

A version bump without a master merge is **not** a publish — users still see the old version. A push to `dev` without a master merge is **not** a publish — `master` is the cache source. A master merge without a version bump is **not** a publish — the cache key doesn't change, so consumers don't refetch. All three steps are required; an unambiguous publish go-signal authorizes all three.

Publishing is reversible-but-visible: nothing is destroyed, but it goes out to other machines. The bar is "user has expressed publish intent for this work," not "user has reconfirmed each git command." Treat unambiguous go-signals — `go`, `ship it`, `publish`, `do it`, `close the loop`, `push` — as authorizing the **entire** three-step publish flow above (plus downstream dependents like update06). Don't re-prompt for sub-steps once intent is clear; that's procedural friction, not safety. Confirm only when intent is genuinely ambiguous (partial work, no version bump in sight, unrelated WIP staged, or the user is mid-thought).

After publish:

- Users with `autoUpdate: true` receive the update on next session start.
- Users without auto-update run `/plugin marketplace update` then `/plugin update`.

### The marketplace landing page (`index.html`) — regenerate at publish time

The repo-root **`index.html`** is the marketplace's public landing page (the GitHub-Pages-style poster listing every plugin and its skills). It is **generated, not hand-edited** — by awesome-kit's plugin-ecosystem skill. Regenerate it with:

```bash
python plugins/awesome-kit/skills/plugin-ecosystem/scripts/generate.py \
  --marketplace plugins-kit --title "plugins-kit marketplace" \
  --output ./index.html --no-open
```

**It crawls the cache, not the dev tree.** `generate.py` reads `~/.claude/plugins/installed_plugins.json` and walks each plugin's **cached `installPath`** (`~/.claude/plugins/cache/<mkt>/<plugin>/<version>/`), filtered by `marketplace.json`. So it reflects the **installed/published** skill roster — **not** unpublished skills sitting on `dev`. Consequence: regenerating `index.html` from a normal session **before** publishing reproduces the *old* landing page (a new skill like `cohesion-audit` won't appear until its plugin version is published and the local cache refetches it).

**Therefore `index.html` regeneration is a publish step, not a dev step.** A dev-branch skill change is not "done" for the landing page until it is published and the page is regenerated. The correct sequence:

1. Publish (version bumps + push dev + merge master), so consumers' — and your own next-session — caches refetch the new versions.
2. In a session where the local cache reflects the published versions (i.e. after a SessionStart bootstrap has updated the cache — clear the cooldown if needed), run the `generate.py` command above.
3. Commit the refreshed `index.html` (to master, where the page is served).

To **preview** the page against unpublished dev skills without publishing, run the generator under a dev-tree-pointed session (`claude-dev` / `pk-dev`, which rewrite `installed_plugins.json` `installPath`s at the dev tree) — but do not commit a dev-preview page as the published landing page.

### Dev-only plugins — do not publish to master

Some plugins live on `dev` for in-development work and must not reach consumers until they are ready. Each such plugin sets `"published": false` in its `plugins/<name>/.claude-plugin/plugin.json`. The marketplace regenerator (`scripts/regen_marketplace.py`) filters those plugins out of `marketplace.json`, so they are excluded structurally — not by memory — even if their files land on master via a cherry-pick.

**Current dev-only plugins** (the field, not this list, is load-bearing — this is just a human-readable inventory):

- `agent-glue` — graph-orchestration kit, design + scaffolding phase. Heavy new Python deps (pydantic, jinja2, jsonschema), no `bootstrap.json` yet, no skills wired up. Tested locally via `--plugin-dir`.
- `workflow-kit` — kit of incremental, native-preserving improvements on top of the native Workflow tool (renamed from `workflow-glue`; 0.2.0). Ships a declarative `*.workflow.yaml` -> native-script compiler (compile-to-native; does not reimplement execution). Adds a generically-named `workflow-kit-agent` executor (extensible) plus script + openrouter node strategies that fulfil a file-passing contract (`$OUT`/`$STATUS`, shell-redirected so payloads bypass the model context — cheap haiku shim, not a deterministic runtime). The openrouter node reuses openrouter-kit's `make_openai_client` runner (`scripts/openrouter_run.py`) + the `openai` SDK (installed into the standalone Python) — both hosted outside workflow-kit, so workflow-kit's only dep stays pyyaml. Domain-skill container (light index + reference docs). Has `bootstrap.json`; tests in `tests/workflow-kit/`. Conceptually supersedes agent-glue's graph-system + claude-dispatch now that the Workflow tool exists.

When you see commits for a dev-only plugin in `git log origin/master..origin/dev`, that's still gotcha 1 territory — branch from master, cherry-pick only the publish-ready commits, and leave the dev-only commits on `dev`. The regenerator is a backstop for the marketplace listing, not a substitute for picking the right commits to merge.

### Pre-publish validation (default)

**Default gate: before any publish, smoke-test the dev working copy with `claudx`.** `claudx` (defined in `~/.bashrc`) launches a `claude` session loading every `plugins/<name>` dir via one `--plugin-dir` each, so the session runs each plugin's skills/hooks/engine **code** straight from disk — no cache, no `installed_plugins.json` change, reverts on exit. Run it, exercise the changed surface (invoke the skill, trigger the hook, run the command), confirm it behaves, then publish.

```bash
claudx        # claude + --plugin-dir for every plugins-kit plugin (see ~/.bashrc)
```

**Known blind spot — manifest content.** Under `--plugin-dir`, the bootstrap engine still reads each plugin's `bootstrap.json` from its **cached** `installPath`, not from disk (insight `plugin_dir_doesnt_test_cross_plugin`). So `claudx` validates code paths but **not** new `bootstrap.json` content (added tools, `download:` recipes, `venv.check_imports`). When your change touches manifest content, escalate to **`claude-dev`** (also in `~/.bashrc`) — it uses `scripts/dev-tree.py` to repoint installPaths at the dev tree, so the engine loads `bootstrap.json` from disk too, then auto-restores normal cache mode on exit.

| Change touches… | Default validator |
|---|---|
| skills / hooks / commands / engine code | `claudx` |
| `bootstrap.json` / manifest content | `claude-dev` (dev-tree mode) |

**Bypassable at your discretion.** This is a default, not a hard gate. Trivial changes — a version-only bump, a doc/CLAUDE.md edit, a single-file mechanical fix — don't need a smoke session; skip it and say so. An unambiguous publish go-signal does not silently waive validation, but you may explicitly bypass when the change can't plausibly break a runtime surface.

### Safe-publish practices

Publishing is the riskiest moment in this repo because it broadcasts to every consumer. Two failure modes have happened, both recoverable but visible (the retraction commits in `git log master` are the scars). Avoid them with these checks.

**Gotcha 1: fast-forwarding dev → master sweeps unrelated commits.** `dev` typically contains in-flight work from other plugins. A fast-forward merge ships *everything* between `master` and `dev`, not just your feature. **Mandatory check before any dev → master merge:**

```bash
git fetch origin
git log --oneline origin/master..origin/dev
```

If that list contains anything beyond the commits you intend to publish, **stop** — do not fast-forward. Pick a safe path instead:

1. **Branch from master, cherry-pick, PR to master.** Cleanest when dev has unrelated WIP. `git checkout -b <feature> origin/master`, cherry-pick the feature commit(s), push, open a PR. Doesn't touch `dev`. After master merges, merge master back into dev to keep dev current.
2. **Wait for the other dev work to ship first.** If those commits are nearly ready, finish their version bumps and publish them properly (every plugin you're shipping needs its own `plugin.json` + `marketplace.json` bump — without that, fresh installs silently diverge). Then publish your feature on top.
3. **Squash-merge a feature branch.** Same as (1) but one squashed commit on master.

Fast-forward `dev` → `master` is only safe when `git log origin/master..origin/dev` shows *exactly* the commits you intend to publish.

**Gotcha 2: `git add <file>` sweeps pre-existing working-tree modifications.** If a tracked file already had uncommitted local edits and you touch it for your feature, `git add <file>` stages *all* the changes in that file, not just yours. The feature commit then ships unrelated WIP. **Mandatory check before any publish commit:**

```bash
git diff --staged
```

Read every line. If anything is unrelated to the feature, `git restore --staged <file>` and use `git add -p` (or `git stash` the WIP first) to stage only the intended hunks. Same discipline for untracked files — don't `git add .` from a dirty tree.

*Sharpening — the dev tree is a live workspace.* The index may already hold **another session's** (or your own earlier) staged work before you touch it. `git add <your specific files>` followed by `git commit` commits the **entire index**, not just the files you named — so a pre-staged rename or WIP rides along under your commit message. The `git diff --staged` check above is the only guard: run it every time and confirm the staged set is *exactly* your files, even when you used a targeted `git add`. (This is how a `workflow-glue → workflow-kit` rename once landed inside an unrelated test-coverage commit.)

**Gotcha 3: a botched publish burns the version number.** Cache entries on consumer machines key off `(plugin, version)`. If a bad version is pushed to master, retracting it doesn't evict caches that already pulled it — same version = same code, forever, from the cache's view. The fix is a patch-bump *past* the burned number (e.g. 0.11.0 broken → don't ship 0.11.1, jump to 0.12.0) so every consumer's cache invalidates cleanly. The 0.11.1 / `patch-bump 4 plugins to force-refresh post-retraction caches` commits on master are an example of this recovery pattern.

**Gotcha 4: unauthorized publish.** A publish go-signal authorizes the full three-step flow (version bumps, push to dev, merge to master). It does **not** authorize sweeping in adjacent unrelated work just because it happens to be staged or sitting on `dev`. If your feature commit is clean but `dev` has other commits, that's gotcha 1 territory — branch from master. The publish authorization is scoped to the work the user actually approved.

**Recovery: how to retract.** A bad publish on master is fixed forward, never with `push --force` to master. Push a follow-up commit that either (a) reverts the bad commit and patch-bumps the affected plugins past the burned version, or (b) re-implements correctly under a new version. Consumers with `autoUpdate: true` then refresh on their next session start. Never rewrite master history — other machines have already fetched it.

**Master drifts behind dev on non-plugin infra — reconcile periodically.** The publish flow cherry-picks *feature* commits (plugin code + version bumps) to master; it never carries the not-tied-to-a-feature changes — a CLAUDE.md gotcha you added while thinking about process, a new test file, a `.gitignore` tweak, dev tooling. So master silently falls behind dev on repo **infrastructure** — including, ironically, the safe-publish gotchas themselves and test coverage for *published* plugins. This is expected (the per-publish scoping in gotcha 4 is what causes it), not a bug — but reconcile it from time to time. Do it in the **master tree**, against `origin/dev`'s committed state (never the live dev working tree), keeping dev-only plugins back:

```bash
git diff --name-only origin/master origin/dev \
  | grep -vE '^(plugins|tests)/(agent-glue|workflow-kit)/' \
  | xargs git checkout origin/dev --
```

Then confirm no dev-only plugin content leaked (`git diff --cached --name-only`), run the brought tests, commit, push master. No version bumps, no `marketplace.json` change — pure infra sync, so consumers are unaffected. Skip the master→dev merge-back when the dev tree is being actively edited: the content already matches on both branches, so the history merge can wait for a calm moment.

**Why both files**: Claude Code uses the `marketplace.json` version to decide whether to fetch a new cache entry. If you only bump `plugin.json` but not `marketplace.json`, consumers won't see the update. The regenerator + a pre-commit hook (`scripts/pre-commit-version-check.sh`) keep them in sync automatically.

**The cache keys on version** — same version = same code. The cache will NOT refresh without a version bump, even if you push new commits. Fresh installs between releases copy HEAD code under the old version string, creating **silent divergence** — two users on the "same version" with different code. The dev-branch strategy above prevents this. Never copy files directly into the plugin cache — always use this publish flow.

**Manifest edits count as code edits.** Adding a tool to `bootstrap.json`, changing a `download:` recipe, bumping a `venv.check_imports` list — all need a version bump too. The engine reads each plugin's `bootstrap.json` from its cached `installPath`, so a manifest edit without a version bump is structurally invisible to consumers (see the `manifest_changes_need_version_bump` insight below).

**Don't omit the version field** hoping for rolling updates. Claude Code substitutes a truncated git SHA, which becomes a static cache key at install time — identical behavior to a version string, with worse readability.

**Downstream consumers with git dependencies** (e.g., update06): If another project depends on `bootstrap` as a Python git dependency (`bootstrap @ git+https://...`), also bump `bootstrap`'s Python package version in `plugins/bootstrap/pyproject.toml`. Without a package version bump, `uv sync` may consider the installed copy satisfied and skip reinstallation even after the lockfile changes.

### update06 — the bootstrap bootstrapper

**Repository**: `kitaekatt/update06` (local: `~/Dev/update06`)

**Purpose**: update06 is a separate marketplace that exists to fix chicken-and-egg problems in plugins-kit. If bootstrap is broken in a way that prevents it from updating itself, update06 provides an independent code path that can repair the situation.

**How it works**: update06 contains a single plugin ("update") whose job is to ensure plugins-kit marketplace is registered and the bootstrap plugin is installed. Its `update_engine.py` is a thin facade that imports `_process_manifest` from `bootstrap_lib` and delegates all real work to it.

**Library dependency**: update06 declares `bootstrap` as a Python git dependency in its `pyproject.toml`:
```
bootstrap @ git+https://github.com/kitaekatt/plugins-kit.git#subdirectory=plugins/bootstrap
```
This installs `bootstrap_lib` into update06's own venv. The venv lives at `~/.claude/plugins/data/update06/update/.venv` and is separate from the bootstrap plugin's cache.

**Three version numbers matter when publishing fixes**:
1. `plugins/bootstrap/.claude-plugin/plugin.json` — plugin version (triggers cache refresh)
2. `.claude-plugin/marketplace.json` — marketplace listing (must match plugin.json)
3. `plugins/bootstrap/pyproject.toml` — Python package version (triggers `uv sync` reinstall in update06's venv)

All three must be bumped for a fix to reach both plugins-kit consumers and update06. After bumping, regenerate update06's lockfile:
```bash
cd ~/Dev/update06/plugins/update
uv lock --upgrade-package bootstrap
```
Then bump update06's own version in both `plugin.json` and `marketplace.json`, commit, and push.

**Always close the loop.** A bootstrap publish is not done until update06 is also bumped, locked against the new bootstrap commit, committed, and pushed. Do not defer the update06 step to "next time" — silent divergence between plugins-kit and update06 defeats the chicken-and-egg fix that update06 exists to provide. If you publish a bootstrap fix in plugins-kit, finish the update06 work in the same session.

**Keep architecture docs current** — when modifying bootstrap behavior, update the bootstrap skill references (`plugins/bootstrap/skills/bootstrap/references/`) to reflect the changes. These are the source of truth for how the system works.

**Anti-pattern: silent bootstrap operations.** Every bootstrap check must log its outcome — `ok_entries` when passing (verbose-only), `action_entries` when remediating (always visible). Adding a check that creates files, clones repos, or writes config without emitting a log entry is a bug. See the "Every check must log its outcome" principle in [engine-internals.md](plugins/bootstrap/skills/bootstrap/references/engine-internals.md).

**Always use `uv run python` in shell scripts** — never bare `python` or `python3`. On Windows, the system PATH contains Microsoft Store stubs (`WindowsApps/python.exe`) that take precedence over any user PATH entry, causing bare `python`/`python3` to fail with "Permission denied" (exit 126) in Git Bash. On macOS, bare `python` often doesn't exist. Since bootstrap guarantees `uv` is available, `uv run python` is the standard way to invoke Python from any shell script in this project. It resolves the correct Python, activates the venv (giving access to installed packages), and works on all platforms.

**Plan non-trivial tasks**: Plan when both (a) the task is non-trivial, and (b) the implementation could go several reasonable directions. Share the plan, get a thumbs-up, then implement. Skip planning when the path is obvious or the user has already framed the approach — in those cases extra ceremony reads as procedural friction, not rigor. When you do plan, use plan mode (`EnterPlanMode`) as the sanctioned space to think and propose; don't ritualize the steps. The goal is alignment on intent, not a checklist.

**Skill-based document placement** (package cohesion): When creating a document, ask "what skill does this belong to?" — the same way you'd ask "what package does this class belong in?" Apply these cohesion principles:

- **CRP (Common Reuse Principle)** — If you use one document in a skill, you should plausibly use them all. Don't force a skill to load content the consumer doesn't need.
- **CCP (Common Closure Principle)** — Documents that change for the same reason belong in the same skill. A schema change should affect one skill, not scatter across several.
- **ADP (Acyclic Dependencies Principle)** — Skills don't circularly depend on each other. The dependency graph is a DAG.

If no existing skill fits, create a stub skill with a description that explains why it exists. The document lives as a reference within the skill and is progressively disclosed (loaded only when the skill is invoked, not upfront).

**Plugin boundaries are hard boundaries for cohesion work.** Never move content between plugins — or into a new plugin — to achieve skill cohesion. Plugins are independently versioned, installed, and bootstrapped units; relocating a skill/reference across a plugin boundary to satisfy CCP/CRP/ADP breaks that independence (cross-plugin caches, dependency edges, version coupling) and is never worth the cohesion gain. Cohesion refactors operate *within* a plugin only. When you spot a genuine cohesion opportunity that spans plugins — two doer-skills in different plugins sharing a subject (e.g. git-kit `git-code-review` + p4-kit `p4-code-review`), a reference duplicated across plugins, a shared substrate two plugins both consume — **surface it as an insight** (a `claude_md:` insight or a note in the relevant skill), do **not** act on it by relocation or by spawning a unifying plugin. Sharing across plugins is done through a library both depend on (e.g. `bootstrap_lib.code_review`), not by merging the skills.

**Reference file design** (within a skill): Apply the same cohesion principles to reference files. Each reference should serve a single audience and change for a single reason. Validate with:

- **CRP test**: "If I load this reference, do I plausibly need all of it?" If a reference mixes engine internals with manifest schema, split it.
- **CCP test**: "When X changes, how many references need updating?" If more than one, the boundary is wrong.

See `plugins/bootstrap/skills/bootstrap/` for the gold standard — 4 references split by audience (engine developers, manifest authors, debuggers, plugin authors) with clean change boundaries.

## Plugin System

Plugins follow the Claude Code plugin spec:
- **Marketplace manifest** (`.claude-plugin/marketplace.json`): Lists available plugins with name, version, source path
- **Plugin manifest** (`.claude-plugin/plugin.json`): Per-plugin metadata (name, version, description, keywords)
- **Skill discovery**: Claude Code scans `skills/` directories for `SKILL.md` files
- **Variable expansion**: `${CLAUDE_PLUGIN_ROOT}` resolves to the plugin's install path at runtime

### Plugin dependencies on bootstrap (declared + guarded)

Every plugin in this marketplace rides on **bootstrap** (venv, `bootstrap_lib`, `uv`, installed config). We make that dependency explicit in **two complementary layers**:

1. **Declared dependency (install-time).** The Claude Code plugin spec supports inter-plugin dependencies — installing a dependent auto-installs/enables its dependencies, blocks disabling a still-needed dependency, and honors version constraints. Every plugin that depends on bootstrap declares it in its `.claude-plugin/plugin.json` as a **bare string** (bootstrap lives in the *same* marketplace, so `name` resolves within `plugins-kit`):
   ```json
   "dependencies": ["bootstrap"]
   ```
   This is the canonical fix for "user installed the plugin without bootstrap." Official docs (source of truth — fetch when in doubt): https://code.claude.com/docs/en/plugin-dependencies and the `dependencies` field in https://code.claude.com/docs/en/plugins-reference.
   - **Same-marketplace deps are bare strings.** Do NOT add a `"marketplace"` field for a dep in this marketplace — that field is *only* for a **different** marketplace and triggers the `allowCrossMarketplaceDependenciesOn` allowlist (a same-marketplace value gets treated as cross-marketplace and can fail installs).
   - **Unversioned on purpose.** A version constraint (`{ "name": "bootstrap", "version": "~0.12" }`) resolves against `{plugin}--v{version}` git tags (`claude plugin tag --push`), which this repo does not use — pinning would cause `no-matching-tag`. Bare = "whatever the marketplace provides."
   - Declare it on every plugin that has a `bootstrap.json` **except** bootstrap itself. Plugins with no `bootstrap.json` (e.g. `cache-kit`) genuinely don't depend on bootstrap — do not add the field.
   - It belongs in **both** `plugin.json` and the generated marketplace entry; `scripts/regen_marketplace.py` propagates it automatically. A `dependencies` edit is a manifest change: it needs a version bump to reach consumers (same rule as any `plugin.json`/`bootstrap.json` edit).

2. **Runtime guard (provision-time).** A declared dependency guarantees bootstrap is *installed*, not that it has *run* — on first install bootstrap provisions each plugin's venv at the next SessionStart (and the cooldown can defer it). For that "installed-but-not-yet-provisioned" window, plugins that would otherwise crash with a raw `ModuleNotFoundError`/missing-interpreter error use the vendored **`bootstrap_guard.py`** (canonical: `plugins/bootstrap/bootstrap_lib/bootstrap_guard.py`). It is **stdlib-only** and **must never import `bootstrap_lib`** (that's the thing that may be missing); it detects absence via the per-plugin `~/.claude/plugins/data/<marketplace>/<plugin>/bootstrap.log` and exits with one actionable "install/enable plugins-kit:bootstrap" message instead of a raw traceback. It is **vendored** per plugin (copied next to the entry script and imported as a plain module), exactly like `path_repair.py`, with a drift test asserting copies match the canonical.

### Hook JSON Format

**Official docs**: https://code.claude.com/docs/en/hooks (canonical reference). When in doubt, fetch this URL — it is the source of truth.

On exit 0, stdout is parsed as JSON. Exit 2 = blocking error (stderr fed to Claude). Other exits = non-blocking error. JSON is only processed on exit 0.

**Universal fields** (all events):

| Field | Default | Description |
|-------|---------|-------------|
| `continue` | `true` | If `false`, Claude stops entirely. Takes precedence over other decisions |
| `stopReason` | none | Message shown to user when `continue` is `false`. Not shown to Claude |
| `suppressOutput` | `false` | If `true`, hides stdout from verbose mode |
| `systemMessage` | none | Shown to user only — Claude never sees it |

**Event-specific decision control**:

| Event | Decision pattern | To Claude |
|-------|-----------------|-----------|
| SessionStart | None | `hookSpecificOutput.additionalContext` or plain text stdout |
| UserPromptSubmit | `decision: "block"` + `reason` | `hookSpecificOutput.additionalContext` or plain text stdout |
| PreToolUse | `hookSpecificOutput.permissionDecision` (allow/deny/ask) | `hookSpecificOutput.additionalContext` |
| PostToolUse | `decision: "block"` + `reason` | `hookSpecificOutput.additionalContext` |
| PostToolUseFailure | None | `hookSpecificOutput.additionalContext` |
| Stop / SubagentStop | `decision: "block"` + `reason` | `reason` only (no `hookSpecificOutput`) |
| SubagentStart | None | `hookSpecificOutput.additionalContext` |
| Notification | None | `hookSpecificOutput.additionalContext` |
| PermissionRequest | `hookSpecificOutput.decision.behavior` (allow/deny) | — |
| ConfigChange | `decision: "block"` + `reason` | — |

`hookSpecificOutput` always requires `hookEventName` set to the event name.

**Background mode** (bootstrap-specific): The engine writes output to a pending file, which the UserPromptSubmit hook reads and outputs as its own stdout. Stop hooks do not support `hookSpecificOutput`, so UserPromptSubmit is used to inject `additionalContext` for Claude.

### Plugin Cache and Registry Layout

Claude Code stores plugin data under `~/.claude/plugins/`:

| Path | Purpose |
|------|---------|
| `cache/{marketplace}/{plugin}/{version}/` | Cached plugin files (copied from marketplace clone) |
| `marketplaces/{marketplace}/` | Git clone of marketplace repo |
| `installed_plugins.json` | Registry of installed plugins (version, gitCommitSha, installPath, scope) |
| `known_marketplaces.json` | Registry of known marketplaces (source, installLocation, lastUpdated, autoUpdate) |
| `data/{plugin}/` | Per-plugin runtime data (config, logs, venv) |

### Debugging

```bash
# Version report — shows local, marketplace, installed, and cached versions for all plugins
bash scripts/plugin-versions.sh

# Run bootstrap engine in console mode (plain text, no JSON, no log writes)
python plugins/bootstrap/engine/bootstrap_engine.py --plugin-root plugins/bootstrap --data-dir ~/.claude/plugins/data/bootstrap --console

# Verbose mode (show ok/cached entries too)
python plugins/bootstrap/engine/bootstrap_engine.py --plugin-root plugins/bootstrap --data-dir ~/.claude/plugins/data/bootstrap --console --verbose
```

## Preferences

- **Never use the memory system** (`~/.claude/projects/*/memory/`). Always update `CLAUDE.md` instead — it is machine-independent and checked into the repo, so all machines and sessions share the same context.

## Insights

```yaml
claude_md:
  _schema_version: "1"
  scope:
    directory: plugins-kit (root)
    covers:
      - dependency management posture across plugins
      - how to install or update plugin dependencies
      - bootstrap engine / hook invocation
    excludes:
      - per-plugin internals (covered by per-plugin CLAUDE.md / bootstrap.json)
  insights:
    - id: bootstrap_json_for_deps
      keywords: [bootstrap.json, plugin dependencies, venv, pyyaml, uv, no manual install, dependency manifest]
      summary: Plugin Python dependencies are declared in bootstrap.json + pyproject.toml and installed by the bootstrap engine using uv. Do not run pip / python -m venv manually.
      detail: |
        Each plugin that ships Python scripts declares its venv requirements in bootstrap.json
        ("venv": { "check_imports": [...] }) and its actual dependencies in pyproject.toml. The
        bootstrap engine creates a venv at ~/.claude/plugins/data/<marketplace>/<plugin>/.venv/
        using uv, installs deps from pyproject.toml, and verifies the check_imports succeed. Do
        not pip install at the user or system level; do not python -m venv manually. If a plugin
        needs a new dep, add it to that plugin's pyproject.toml and update check_imports in
        bootstrap.json.
      origin: User directive 2026-04-28 during YAML contract refactor; existing pattern in unreal-kit/bootstrap.json + p4-kit/bootstrap.json.
      added: "2026-04-28"
    - id: run_bootstrap_hook_directly
      keywords: [bootstrap hook, sessionstart, force update, plugin refresh, install update]
      summary: To force a plugin install or update outside a normal session start, run the bootstrap hook directly.
      detail: |
        The bootstrap hook lives at plugins/bootstrap/hooks/sessionstart/session-bootstrap.sh
        and is the entry point Claude Code calls on SessionStart. To force-refresh plugins or
        re-run dependency installs, invoke it directly via bash. The engine reads the layered
        bootstrap.json hierarchy, runs the manifest+script phases, and emits the same hook JSON
        it would on a real session start. Useful when a plugin's bootstrap.json has changed and
        you need the venv refreshed before the next session.
      origin: User directive 2026-04-28.
      added: "2026-04-28"
    - id: bootstrap_cooldown_reset
      keywords: [cooldown, bootstrap not running, force bootstrap, plugin update not applying, last_run_epoch, bootstrap-reset-cooldown, silent skip, no bootstrap log]
      summary: Bootstrap throttles itself per-project via a cooldown file; clear it with bootstrap-reset-cooldown.sh when bootstrap appears to be ignoring you.
      detail: |
        After bootstrap runs for a project it writes ~/.claude/plugins/data/plugins-kit/bootstrap/cooldowns/last_run_epoch.<sha1-of-cwd>.
        Subsequent SessionStart hooks within the cooldown window skip bootstrap entirely -- no
        log entry, no checks, no remediation. Symptoms: a published plugin update doesn't take
        effect, a bootstrap.json change isn't applied, or a plugin's bootstrap.log is stale.
        Reset with `bash plugins/bootstrap/scripts/bootstrap-reset-cooldown.sh` (current
        project), `--all` (every project), or `--status` (list cooldowns + ages, no writes).
        Do not confuse with bootstrap_cache.sha256 (the per-check content-hash cache); the
        cooldown is the bigger hammer and the right tool 99% of the time. See the "Bootstrap"
        section above for full context.
      origin: User directive 2026-05-05 -- documentation gap surfaced when a unreal-kit publish appeared not to apply.
      added: "2026-05-05"
    - id: host_python_via_plugin_venv
      keywords: [host-side python, plugin venv, uv run python, ModuleNotFoundError, foreign cwd, project root, pyyaml, skill examples]
      summary: SKILL.md examples that invoke host-side Python must use the explicit plugin-venv path, not `uv run python`, when the documented cwd is the user's project root.
      detail: |
        `uv run python` resolves the venv from the cwd's pyproject.toml. When a skill instructs
        the user to run from a project root that has no matching pyproject.toml (e.g. an
        Unreal project root, where p4 picks up .p4config.txt), uv falls back to a bare
        interpreter without the plugin's installed dependencies and the script crashes with
        ModuleNotFoundError. Bootstrap installs each plugin's venv at a stable canonical path:
          Windows: ~/.claude/plugins/data/<marketplace>/<plugin>/.venv/Scripts/python.exe
          macOS/Linux: ~/.claude/plugins/data/<marketplace>/<plugin>/.venv/bin/python
        The path does not change across plugin versions and resolves correctly from any cwd.
        Use it directly in SKILL.md examples instead of `uv run python`.
      origin: "Surfaced 2026-05-05 in unreal-kit fix-up-redirectors -- broke Phase 2 with ModuleNotFoundError: yaml. Fixed in 0.9.4."
      added: "2026-05-05"
    - id: manifest_changes_need_version_bump
      keywords: [bootstrap.json, manifest change, version bump, cache key, silent divergence, download recipe, dead config, install path, installPath]
      summary: Edits to bootstrap.json (or any per-plugin manifest) need a version bump to reach consumers, same rule as code changes -- the engine reads each plugin's bootstrap.json from its cached installPath.
      detail: |
        The bootstrap engine's per-plugin loop reads `bootstrap.json` from the plugin's
        `installPath` recorded in `~/.claude/plugins/installed_plugins.json`. That installPath
        is the cache directory (`~/.claude/plugins/cache/<mkt>/<plugin>/<version>/`), keyed on
        version. Adding a new tool, a `download:` block, a new venv import, etc. to bootstrap.json
        without bumping the plugin version means consumers still see the OLD bootstrap.json
        from their cache. The new manifest content is structurally invisible until a version
        bump triggers a cache refresh. Same "burned version" failure mode as code changes
        (CLAUDE.md gotcha 3). Surfaced when the tool-resolution redesign added jq's download
        recipe to bootstrap.json on dev without bumping bootstrap's version -- master and dev
        both showed v0.10.14 with completely different bootstrap.json content. Recovery: bump
        to a fresh version (e.g. 0.10.14 -> 0.11.0) and republish.
      origin: "Surfaced 2026-05-27 while smoke-testing the tool-resolution redesign via claudx (--plugin-dir all dev plugins). jq/gh never got download-recorded because the engine was reading the cached 0.10.14 bootstrap.json which had no download: block."
      added: "2026-05-27"
    - id: plugin_dir_doesnt_test_cross_plugin
      keywords: [--plugin-dir, claudx, smoke test, cross-plugin, bootstrap testing, installPath, dev tree, cache, layered manifests]
      summary: --plugin-dir overrides Claude Code's load of one plugin from disk, but the bootstrap engine's per-plugin iteration still reads OTHER plugins' bootstrap.json from their cached installPath.
      detail: |
        Loading a plugin via `--plugin-dir <dev tree>` only overrides Claude Code's loading of
        THAT plugin's hooks/skills. The bootstrap engine's per-plugin loop iterates
        `installed_plugins.json` and reads each plugin's bootstrap.json from its cached
        installPath. So when claudx loads all 12 dev plugins via --plugin-dir, the engine
        still sees each plugin's CACHED bootstrap.json -- not the dev-tree version.
        Implication: --plugin-dir smoke tests can exercise the new engine code paths (the
        engine binary is loaded from dev), but they cannot exercise new bootstrap.json content
        for any plugin without first publishing that plugin. Workarounds: (a) bump versions
        and publish to test for real; (b) use the `pk-dev` mode helper, which rewrites
        installed_plugins.json to point installPaths at the dev tree -- that does exercise
        new bootstrap.json content; (c) test new bootstrap.json content via layered manifests
        in `~/.claude/bootstrap.json` or `<project>/.claude/bootstrap.json`, which DO go
        through the engine without an installPath lookup.
      origin: Surfaced 2026-05-27 -- the claudx smoke test couldn't validate jq's new download recipe because the engine kept reading the cached bootstrap.json.
      added: "2026-05-27"
    - id: code_review_cross_plugin_cohesion
      keywords: [code-review domain, git-code-review, p4-code-review, cross-plugin cohesion, bootstrap_lib.code_review, dec_13, domain not built, inter-plugin opportunity, surface not merge]
      summary: git-kit:git-code-review + p4-kit:p4-code-review are dec_13-justified doer-skills sharing one subject, but they are deliberately NOT merged into a domain -- the members live in different plugins, and plugin boundaries are hard boundaries for cohesion work. Recorded as an inter-plugin cohesion observation, not acted on.
      detail: |
        Both are technique-skills running the same pre-submit multi-agent review pipeline
        (identical reviewer roster, profiles, validators, submit-gate format); they differ only
        in VCS front-half (git ranges/auto-detect vs p4 changelist/shelving). The dec_13 merge
        criterion (2+ doers sharing a subject) is satisfied, and the VCS-neutral back-half
        (chunking + CLAUDE.md collection + submit-gate parsing) is ALREADY shared via
        plugins/bootstrap/bootstrap_lib/code_review/ (chunking.py + claude_mds.py). So the old
        "needs a shared abstraction first" blocker is gone. They are still NOT merged because:
        (1) the members are in separate plugins (git-kit, p4-kit) and a domain router cannot
        span plugins without relocating a member or spawning a new home plugin -- both barred by
        "Plugin boundaries are hard boundaries for cohesion work" above; (2) routing value is low
        -- git-vs-p4 is unambiguous from the workspace, so a natural-language front door adds
        little over the two already-auto-triggering skills. Correct cross-plugin sharing is the
        library both depend on (bootstrap_lib.code_review), which already exists. Do not
        re-investigate a code-review domain; the answer is "surface, don't merge."
      origin: Surfaced 2026-05-31 during the cohesion refactor -- after W2-proper, an Explore feasibility sweep found the shared lib already exists; user ruled cross-plugin relocation/new-plugin out of bounds for cohesion work.
      added: "2026-05-31"
  conventions:
    - rule: When adding a new plugin Python dependency, update <plugin>/pyproject.toml AND <plugin>/bootstrap.json venv.check_imports together.
      keywords: [pyproject.toml, bootstrap.json, dependency, venv, check_imports]
      why: pyproject.toml drives the actual install (via uv); check_imports tells the bootstrap engine what to verify post-install. Skipping check_imports leads to silent install failures.
    - rule: Never invoke pip, python -m venv, or any other Python package manager manually for plugin dependencies.
      keywords: [no manual install, pip, venv, plugin deps, bootstrap-only]
      why: Plugin dependency installs go through the bootstrap engine so they end up in the right per-plugin venv at ~/.claude/plugins/data/<marketplace>/<plugin>/.venv/. Manual installs land in the wrong location and confuse the engine's cache.
    - rule: Always run /git-code-review on non-trivial changelists before committing.
      keywords: [git-code-review, code review, pre-commit, non-trivial CL, multi-file commit, before submit, multi-agent review]
      why: Multi-agent review catches bugs and CLAUDE.md violations the author may miss; running it before commit lets the author fix issues in the same staging cycle rather than after the fact. "Non-trivial" = anything beyond a single-file mechanical change (typo fix, version bump). When in doubt, run it.
```
