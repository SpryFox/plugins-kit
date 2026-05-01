# Domain layering

A domain-skill that owns a knowledge area large enough to decompose into 2+ semi-independent sub-areas needs a layering surface: the user-facing mechanics that route a request into the right sub-area without forcing the agent to re-orient on every invocation.

Use when a domain-skill has multiple sub-domains the user navigates between -- e.g. an engine-automation skill with sub-areas for asset inspection, level authoring, and PIE control; a project-management skill with sub-areas for tickets, milestones, and approvals. Do not use for a single-area domain-skill; the layering machinery has cost (a greeting menu, dispatch logic, registration index) that is wasted when only one area exists.

## Surface mechanics

A domain-skill with sub-domains exposes four user-facing behaviors. Each addresses a distinct invocation shape.

### 1. Bare-invocation greeting menu

When the user invokes the skill with no follow-up request (e.g. `/some-domain` alone), greet with a sub-domain menu rather than dumping content. The menu lets the user pick the sub-area that matches their intent.

**Format:**

```
How can I help you with <domain>?
 - <sub-domain-A description> (`/<skill> <keyword>`)
 - <sub-domain-B description> (`/<skill> <keyword>`)
 - ...

Or can I help you with something else?
```

Show every registered sub-domain. Do NOT dump operations tables, references, or other detail at this point -- the menu is the entire response, and the user picks next.

### 2. Argument dispatch

When the user invokes the skill with a domain argument (e.g. `/some-domain assets` or `/some-domain pie`), skip the greeting and jump directly into that sub-domain's capability surface. Match the argument against the sub-domain's `keyword_cues` cluster, name, or description.

The argument-dispatch path produces a sub-domain capabilities table immediately, as if the user had selected from the greeting menu.

### 3. Domain overview request detection

Before responding to any sub-domain request, ask: *is the user asking what this sub-domain can do, or asking to do something specific?* The two invocation shapes warrant different responses.

A **domain overview request** is a capability question -- the user wants to see what's available, not execute anything yet. Examples:

- "what <area> operations can you perform"
- "what can you do with <area>"
- "list <area> commands"
- "help me with <area>" (no specific task named)
- "<area> options"
- any phrasing that asks what's available rather than naming an action

When the request is a domain overview request, respond with **only** the matching sub-domain's capabilities table (name + description per capability). No extra commentary. No CLI examples. No design principles. No follow-up question like "want me to run one?". The table is the entire response, and the user picks the capability they want.

For requests that name a specific action ("run the inspector", "rebuild the index"), skip the overview table and execute the capability using normal judgment.

### 4. Sub-domain registration

Sub-domains are declared in a machine-readable index inside the SKILL.md or in a dedicated reference file. Each entry carries:

- `name` -- canonical sub-domain identifier
- `description` -- one sentence on the sub-domain's scope
- `keyword_cues` -- list of phrases that route to this sub-domain
- `reference` -- path to the sub-domain's deeper documentation

Example index shape:

```yaml
sub_domains:
  - name: subdomain-A
    description: First sub-area description.
    keyword_cues: [keyword-a, keyword-a-alt, alt-cue]
    reference: references/subdomain-a.md
  - name: subdomain-B
    description: Second sub-area description.
    keyword_cues: [keyword-b, keyword-b-alt]
    reference: references/subdomain-b.md
```

The index is the source of truth for the greeting menu and for argument-dispatch matching. Tooling that audits the domain-skill consumes this index to verify each declared sub-domain has a reachable reference doc.

## Sub-agent dispatch convention

When a domain-skill ships alongside a paired sub-agent named `<skill-name>-a`, the agent is configured to invoke the skill on session start so the agent always has the domain's vocabulary and reference index available. This is the agent-bundled attribute on the skill.

The invariant: a sub-agent paired with a domain-skill never loads the skill manually mid-session. The parent skill loads the agent; the agent always invokes the skill on entry. This prevents "the sub-agent didn't know about X" failure modes.

The convention extends to dispatch: when a parent task calls for a sub-agent, the parent invokes `<skill-name>-a` rather than spawning a generic agent and instructing it to invoke `/<skill-name>` manually. Generic agents that load the skill manually defeat the agent-bundled invariant.

**Audit gate:** if a domain-skill has a paired `<skill-name>-a` agent, the SKILL.md must declare the dispatch convention explicitly so that anyone composing with the agent (or any future contributor adding new agents) knows the parent-spawns-bundled rule rather than the parent-spawns-generic-and-loads rule.

## Worked example: hypothetical project-management domain

A `/project-mgmt` domain-skill with three sub-domains -- tickets, milestones, approvals -- declares its layering as follows:

**SKILL.md sub-domain index:**

```yaml
sub_domains:
  - name: tickets
    description: ticket creation, triage, status transitions
    keyword_cues: [ticket, issue, bug report, task, triage]
    reference: references/tickets.md
  - name: milestones
    description: milestone planning, dependency tracking, due-date management
    keyword_cues: [milestone, sprint, release, deadline, schedule]
    reference: references/milestones.md
  - name: approvals
    description: approval routing, sign-off tracking, escalation
    keyword_cues: [approval, sign-off, review request, escalate]
    reference: references/approvals.md
```

**Bare invocation `/project-mgmt`:**

```
How can I help you with project management?
 - ticket creation, triage, status transitions (`/project-mgmt tickets`)
 - milestone planning, dependency tracking, due-date management (`/project-mgmt milestones`)
 - approval routing, sign-off tracking, escalation (`/project-mgmt approvals`)

Or can I help you with something else?
```

**Argument dispatch `/project-mgmt tickets`:**

(skips greeting; shows tickets capabilities table)

**Domain overview request "what can I do with milestones":**

(matches keyword_cues of `milestones`; responds with milestones capabilities table only, no extra commentary)

**Specific action "create a ticket for the auth bug":**

(matches `ticket` keyword cue; skips overview; routes to ticket-creation capability and executes)

## Worked example: hypothetical inventory domain

An `/inventory` domain-skill with two sub-domains -- character-inventory and world-pickup -- with a paired `inventory-a` sub-agent:

**SKILL.md** declares both the sub-domain index and the dispatch convention:

```
For any inventory-domain work that warrants a subagent, spawn the
`inventory-a` subagent. It always invokes /inventory at the start, so
it already has this skill loaded. Do not spawn a generic subagent and
tell it to invoke /inventory manually -- use inventory-a instead.
```

The dispatch paragraph is required because there is a paired agent. Without it, a future contributor composing with sub-agents would not know to use `inventory-a` and would default to a generic agent + manual skill load.

## Audit hooks

A domain-skill claiming the layering pattern must satisfy these auditable conditions:

- Sub-domain index present, machine-readable, and consumable for greeting/dispatch/overview-detection logic.
- Each declared sub-domain has a reachable reference file (no broken references).
- Bare-invocation greeting documented in SKILL.md.
- Overview-vs-action detection rule documented in SKILL.md.
- If a `<skill-name>-a` agent exists, the dispatch convention is declared explicitly.

Single-area domain-skills do not satisfy this pattern -- and should not. Forcing the layering surface onto a single-area domain adds noise without orientation benefit.
