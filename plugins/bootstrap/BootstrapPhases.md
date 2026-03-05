# Bootstrap Phases — Observed Behavior

This document describes the **actual** phases Claude Code goes through from a clean install to a running bootstrap plugin, based on live testing (wiping `~/.claude/plugins/` and observing each restart).

---

## Phase 1: Marketplace Sync

**Trigger**: Claude Code starts with `additionalKnownMarketplaces` pointing to the plugins-kit repo (configured in settings).

**What happens**:
- Claude Code clones the marketplace repo to `plugins/marketplaces/plugins-kit/`
- Records it in `plugins/known_marketplaces.json` with source URL, install location, and `lastUpdated` timestamp
- No plugins are installed yet

**State after Phase 1**:
```
plugins/known_marketplaces.json     ← marketplace registered
plugins/marketplaces/plugins-kit/   ← full repo clone
plugins/installed_plugins.json      ← {"version": 2, "plugins": {}}
```

---

## Phase 2: Plugin Install + Bootstrap Hook

**Trigger**: Claude Code starts again (second run). Marketplace is known; Claude Code installs enabled plugins.

**What happens**:
1. Plugin files copied to `plugins/cache/plugins-kit/bootstrap/0.1.0/`
2. Entry written to `plugins/installed_plugins.json`:
   - `scope`: project
   - `installPath`: cache path
   - `version`: 0.1.0
   - `gitCommitSha`: pinned to the commit at install time
   - `projectPath`: active project path at install time
3. Bootstrap plugin's SessionStart hook fires (`session-bootstrap.sh`)
4. Hook detects no Python 3 → downloads `cpython-3.12.9+20250317` from python-build-standalone → extracts to `~/.local/share/python-standalone/`
5. Bootstrap engine runs

**State after Phase 2**:
```
plugins/cache/plugins-kit/bootstrap/0.1.0/   ← plugin files cached
plugins/installed_plugins.json               ← bootstrap@plugins-kit entry
~/.local/share/python-standalone/            ← standalone Python runtime (~3500 files)
```
