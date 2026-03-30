# plugins-kit auto-update disabled workaround

## Problem

Many early plugins-kit users had the marketplace registered in `known_marketplaces.json` with `autoUpdate: false`. This meant the marketplace clone never refreshed, so plugin updates (including bootstrap fixes) never reached those users.

## Workaround

A separate marketplace, **update06**, provides an independent update path that doesn't depend on plugins-kit being auto-updated.

### Chain

1. **Project settings** enables `update@update06` and registers the update06 marketplace:
   ```json
   // <project>/.claude/settings.json
   {
     "enabledPlugins": { "update@update06": true },
     "extraKnownMarketplaces": {
       "update06": {
         "source": { "source": "git", "url": "https://github.com/kitaekatt/update06.git" },
         "autoUpdate": true
       }
     }
   }
   ```

2. **update06:update** SessionStart hook runs and processes `update.json`, which:
   - Registers the plugins-kit marketplace with `autoUpdate: true` (via `json_entries` merge into `known_marketplaces.json`)
   - Installs `plugins-kit:bootstrap` as a user-scoped plugin

3. **plugins-kit:bootstrap** SessionStart hook runs and processes the project's `.claude/bootstrap.json`, which declares additional plugins to install (e.g. `plugins-kit:unreal-kit`):
   ```json
   // <project>/.claude/bootstrap.json
   {
     "marketplaces": [
       { "name": "plugins-kit", "source": "https://github.com/kitaekatt/plugins-kit.git", "alwaysUpdate": true }
     ],
     "plugins": [
       { "ref": "plugins-kit:bootstrap", "enabled": true, "scope": "user" },
       { "ref": "plugins-kit:unreal-kit", "enabled": true, "scope": "user" }
     ]
   }
   ```

### Result

After a single session start, the user ends up with:
- plugins-kit marketplace registered with auto-update enabled
- `plugins-kit:bootstrap` installed at user scope
- Any project-declared plugins (e.g. `plugins-kit:unreal-kit`) installed at user scope
- Future sessions auto-update both marketplaces and all plugins

### Why update06 exists separately

update06 solves a chicken-and-egg problem: if bootstrap itself is broken or outdated, it can't update itself. update06 provides an independent code path — it imports `bootstrap_lib` as a Python git dependency and delegates to `_process_manifest()`, but its own marketplace and cache are completely separate from plugins-kit.
