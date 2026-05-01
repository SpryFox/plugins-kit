# Query-tool facade pattern

A domain that maintains a gazetteer or inventory -- a structured catalog of entities the agent and the user reference repeatedly -- benefits from a fast lookup tool wrapping the catalog. The query-tool facade pattern names the convention.

Use when a domain has a catalog that fits any of:

- An entity index that the agent or user references by name or ID frequently (e.g. a directory of NPCs, items, characters, rooms, configurations, accounts).
- A flat list of records the user routinely searches by substring or partial spelling.
- A dataset where exact-match lookups would otherwise force the agent to grep the codebase or read raw files.

Do not use when the catalog is small enough that the agent loads it whole into context, or when lookups are rare enough that bespoke greps are cheaper than maintaining a dedicated tool.

## Convention

A single facade script with multiple lookup modes wraps the catalog. The script auto-indexes the underlying data on load (or maintains a companion index file) so lookups are fast.

```
catalog_lookup.py <mode> <args...>
```

Modes typically include:

- `<entity-type> <query>` -- exact match by ID or name (e.g. `catalog_lookup.py user alice42`)
- `<entity-type> <category-name>` -- exact match by category attribute
- `list [--substring <fragment>]` -- enumerate entries; `--substring` filters

The exact mode names are domain-specific. The convention is the shape: a single script with multiple modes, structured arguments, deterministic indexing.

## Did-you-mean on miss

When a lookup misses, the script returns a `did_you_mean:` list with 5-10 close suggestions ranked by edit distance, substring overlap, or some other proximity heuristic. The script does NOT silently resolve misspellings -- it surfaces the suggestions and lets the agent or user pick.

This rule pays off in two ways:
- The agent learns the canonical spelling without prompting, because the next attempt uses a value from the suggestions list.
- The user sees their typo as a typo rather than as a silent wrong-match.

```yaml
# Output on miss:
status: not_found
query: alic42
did_you_mean:
  - alice42
  - alex42
  - alicia42
```

## YAML output

All query results are YAML structured data. Not raw text, not JSON, not markdown tables. YAML is human-readable, agent-parseable, and pasteable into a follow-up prompt without escaping.

The agent can render the YAML to the user as-is or extract specific fields for downstream use. Either way the contract is stable: every query mode emits YAML.

## Spelling-discovery discipline

The agent's discipline when interacting with the catalog:

1. If unsure of the canonical spelling of an entity name, run `list --substring <fragment>` first to enumerate matches.
2. Accept `did_you_mean:` suggestions from a missed lookup before attempting any grep, file scan, or codebase search for the spelling.
3. Do NOT hardcode spelling assumptions when invoking the catalog tool. The catalog is the source of truth; spelling-from-memory is a failure mode.

This discipline matters because the agent's training-data-style spelling guesses (which often disagree with project-specific conventions) silently corrupt downstream operations when they pass to a tool that doesn't validate. The query tool's strict-match-then-suggest contract makes the spelling failure visible.

## Worked example: hypothetical user-directory query tool

A capability-skill `/user-directory` ships a `user_lookup.py` query tool wrapping a user catalog:

```bash
user_lookup.py user <id-or-name>           # exact match by user ID or display name
user_lookup.py team <team-id>              # exact match by team
user_lookup.py role <role-name>            # exact match by role
user_lookup.py list [--substring <frag>]   # enumerate; substring filter
```

Hit case:

```yaml
# user_lookup.py user alice42
user_id: alice42
display_name: Alice Example
team: platform
role: senior_engineer
status: active
```

Miss case with did-you-mean:

```yaml
# user_lookup.py user alic42
status: not_found
query: alic42
did_you_mean:
  - alice42
  - alic-three
```

Spelling-discovery flow: the agent needs to look up "the user named ali something" but cannot remember the canonical id. Rather than grep, the agent runs `list --substring ali` and accepts a result from the enumerated set.

## Worked example: hypothetical config-entry query tool

A domain that wraps a project's configuration files exposes a `config_lookup.py` query tool:

```bash
config_lookup.py entry <key>                # lookup a config entry by key
config_lookup.py section <section-name>     # list all entries in a section
config_lookup.py list [--substring <frag>]  # enumerate keys
```

The tool auto-indexes the YAML config tree at startup; lookups are O(1) on a hash. Misses surface did_you_mean for typo recovery.

## Audit hooks

A domain that claims this pattern must satisfy:

- The query-tool script exists at the documented path and is executable from the project root.
- The script has a stable mode-and-args interface; mode names are documented in the SKILL.md.
- All output is YAML on both hit and miss paths.
- Misses produce a `did_you_mean:` list (or an explicit `did_you_mean: []` when no near matches exist).
- The SKILL.md or a reference doc declares the spelling-discovery discipline so the agent's behavior is documented.

The pattern fits naturally with a capability-skill's `subdomain_config:` (when the catalog spans sub-areas with per-sub-area state vocabulary) and with the actions pattern (when a multi-step recipe captures fields from a query result for use in later steps).
