# Case Study: update01/bootstrap

Marketplace sync and plugin cache refresh. Currently lives in its own marketplace (`update01`) — under the new system, this becomes the bootstrap plugin's own self-bootstrap logic.

## Current Operations

### Automatable

| Category | Condition | Check Method | Remediation |
|----------|-----------|-------------|-------------|
| Configuration | Known marketplaces JSON lacks expected entries | Compare reference `known_marketplaces.json` against `~/.claude/plugins/known_marketplaces.json` | Additive JSON merge (add missing entries, update `source`/`autoUpdate`, preserve runtime fields) |
| Plugin | Plugin out of date (`plugins-kit:unreal-kit`) | Time-based throttle (16 hours) | `claude plugin update --scope <scope> plugins-kit:unreal-kit` |

### Manual

None — update01 has no manual operations. Everything is fully automatable.

## Manifest (`bootstrap.json`)

All operations are expressible as manifest entries — no bootstrap script needed:

```json
{
  "json_entries": [
    {
      "reference": "known_marketplaces.json",
      "target": "~/.claude/plugins/known_marketplaces.json",
      "merge_fields": ["source", "autoUpdate"],
      "preserve_fields": ["lastUpdated", "installLocation"]
    }
  ],
  "plugins": [
    {"ref": "plugins-kit:unreal-kit", "enabled": true}
  ]
}
```

## Bootstrap Script

None needed. The manifest covers both operations completely:

- **Marketplace registration**: The `json_entries` field handles the additive merge — same `ensure_json_entries()` primitive, just driven by the engine instead of script code.
- **Plugin freshness**: The `plugins` field with `enabled: true` tells the engine to ensure the plugin is installed and up to date, using its built-in freshness check with time-throttling.

## Library Usage

| Source | Operation | Primitive |
|--------|-----------|-----------|
| Manifest | Sync marketplace registrations | `ensure_json_entries()` |
| Manifest | Ensure plugin installed and fresh | `check_plugin_freshness()` + `update_plugin()` |

## Observations

- Pure manifest — zero lines of bootstrap code
- No manual operations — everything is automatable
- The managed plugin list is now data-driven via the manifest instead of hardcoded in a bash script
- Under the new system, this doesn't need its own marketplace — it's just the bootstrap plugin's own logic
- `ensure_json_entries()` is a general-purpose primitive: takes a reference file, a target file, fields to merge, and fields to preserve. Useful beyond marketplace sync.
- Plugin freshness check improves on pure time-throttle by using `git ls-remote` to avoid unnecessary updates when nothing changed
- This case study demonstrates the key value of the hybrid model: common operations need no code at all
