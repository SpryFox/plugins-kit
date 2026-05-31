---
name: unreal-domain
author: christina
skill-type: domain-skill
description: Use when automating Unreal Engine -- reading/writing data, MCP editor control, or redirector cleanup. Do NOT use for C++/Blueprint work.
---

# Unreal Engine Automation

The domain for automating Unreal Engine from a Claude agent. Three skills share one UE runtime (the unreal-kit
venv + project/engine discovery) and split across two execution channels — host-side Python and in-Editor MCP.
Say what you want — "read this asset's properties", "spawn an actor in the level", "clean up redirectors" — and
this domain routes you to the right member.

The members are independent skills and keep their own triggers/commands; this domain adds the natural-language
entry, the shared-runtime orientation, and the map among them.

## Routing

| You want to… | Member skill | Channel | Editor must be… |
|---|---|---|---|
| read / write / extract asset or property **data** via Python | `ue-python-api` | host-side Python (`ue_runner`) | open *or* closed |
| **drive the live Editor** — spawn actors, author graphs, drive PIE | `ue-mcp-server` | in-Editor MCP | open + MCP server running |
| clean up **ObjectRedirector** assets in a P4-backed project | `fix-up-redirectors` (`/fix-up-redirectors`) | host-side Python + P4 | open *or* closed |

## Domain contract

```yaml
domain_skill:
  _schema_version: "1"
  identity: The Unreal Engine automation domain -- routes among Python data access, in-Editor MCP control, and ObjectRedirector cleanup over a shared UE runtime (the unreal-kit venv + project/engine discovery).
  companions:
    siblings: []
    note: |
      No sibling domains. The members share the unreal-kit lib/ runtime; this domain orients and routes
      among them. It does not duplicate their deep procedures.
  scope:
    covers:
      - routing UE-automation intent to the right member (data access vs Editor control vs redirector cleanup)
      - the shared runtime substrate (the unreal-kit venv, project/engine discovery, the two execution channels)
      - orienting a fresh agent on host-side Python vs in-Editor MCP
    excludes:
      - the deep per-skill procedures, recipes, and reference docs (they live in the member skills)
      - C++ or Blueprint-graph work (this domain is Python/MCP automation only)
      - project-specific asset paths, class names, or workflows (unreal-kit is engine-generic)
  orientation:
    summary: |
      Three members over one runtime. ue-python-api reads/writes/extracts Editor data via the host-side
      ue_runner (auto-detects Editor: remote over upyrc when open, headless commandlet when closed).
      ue-mcp-server drives a live Editor imperatively (spawn actors, author graphs, PIE) through the MCP
      client -- requires the Editor open with its MCP server running. fix-up-redirectors cleans
      ObjectRedirectors in a P4-backed project using the host-side runner plus P4. Pick the member by what
      you are doing and whether the Editor must be live (see the Routing table and shared-runtime.md).
    behavioral_guardrails:
      - Pick the channel by the task -- data access and redirector cleanup run host-side (Editor optional); live-Editor control (spawn/graphs/PIE) needs ue-mcp-server with the Editor + MCP server running.
      - Engine-generic only. Never add project-specific asset paths, class names, or workflows to any member or this domain -- unreal-kit is a public MIT plugin.
      - All host-side Python runs in the shared unreal-kit venv that bootstrap provisions; do not pip-install at the system level.
  index:
    references:
      - id: shared_runtime
        path: references/shared-runtime.md
        keywords: [shared runtime, ue venv, project discovery, host-side python, in-editor mcp, ue_runner, ue_mcp_client, execution channels]
        summary: The shared UE runtime substrate (the unreal-kit venv + project/engine discovery) and the two execution channels (host-side Python via ue_runner vs in-Editor MCP via ue_mcp_client), with the channel-to-member mapping.
    members:
      - name: ue-python-api
        type: capability-skill
        ref: ue-python-api
        keywords: [unreal python, asset inspection, property read write, reference graph, ue_runner, commandlet, remote]
      - name: ue-mcp-server
        type: capability-skill
        ref: ue-mcp-server
        keywords: [mcp server, spawn actors, author graphs, drive pie, live editor control]
      - name: fix-up-redirectors
        type: technique-skill
        ref: /fix-up-redirectors
        keywords: [object redirector, redirector cleanup, p4-backed, fix up redirectors]
```

## Cross-references

- **Shared runtime** — `references/shared-runtime.md`.
- **Members** — `ue-python-api` (Python data access), `ue-mcp-server` (MCP editor control), `/fix-up-redirectors` (redirector cleanup).
