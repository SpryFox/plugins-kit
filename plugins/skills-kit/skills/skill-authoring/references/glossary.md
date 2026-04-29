# Skill Glossary

Canonical terms for skill authoring in this project. Use these terms verbatim
in skill documentation, framework references, and conversation about skill
design. When a contributor uses different language, re-phrase in these terms
to keep usage consistent.

This glossary defines vocabulary only. The contracts that bind these terms
into rules — what a given skill type must contain, recommend, or prohibit —
live in `skill-types-framework.md`.

Sections are grouped by what they describe:

- **Material** — what a skill is physically made of (Files, Conventions, External binding).
- **Method** — the design vocabulary applied to material (Principles, Patterns).
- **Skill types** — contracts that compose material and method into auditable categories.
- **Orthogonal attributes** — independent flags that apply across types.

The first two are wrapped sections containing related sub-sections; the
last two are flat top-level sections. Within and across groupings,
sections follow bottom-up composition (see Principles): each section
depends only on terms defined above.

---

## Material

What a skill is physically made of, both on disk and in runtime wiring.

### Files

The on-disk artifacts inside a skill directory.

**SKILL.md file**
The required main file of every skill. Holds the YAML frontmatter and the
markdown body. The L2 layer of progressive disclosure: loaded only when a
skill's trigger matches.

**Reference file**
Supplementary markdown in the skill directory, linked from SKILL.md and
loaded on demand when its link is followed. The L3 layer of progressive
disclosure. Reference files should be one hop deep from SKILL.md, not
nested — Claude tends to read partial content from deeply-nested references.

**Script**
An executable file (Python, shell, etc.) shipped inside a skill. The agent
runs the script via bash but never loads its contents into the conversation;
only the script's stdout/stderr enters context. Do not confuse the *script*
file block with the `trigger: user-only` attribute — a script is a file you
ship; user-only is how a skill is invoked.

**Template / asset**
A non-executable resource: a `template.docx`, a `config.json`, a lookup
table CSV. Loaded only when SKILL.md instructs the agent to read it.

---

### Conventions

The named sections and patterns that appear inside a SKILL.md file or a
reference file.

**Frontmatter**
The YAML header at the top of a SKILL.md file. Holds `name` (≤64 chars,
lowercase letters/numbers/hyphens, no reserved words "anthropic" or
"claude"), `description` (≤160 chars; see Trigger entry for content rules),
and optionally `allowed-tools` and `metadata`.

**Trigger**
The directive clause inside the `description` field. The single signal
Claude uses to decide whether to load the skill, and the only purpose
the description serves. A trigger must:

- Be **directive**: "Use when..." or "Invoke when...". Capability
  summaries ("Enables...", "Provides...", "Manages...") cause Claude to
  follow the description instead of reading the body.
- Name a **clear, unambiguous condition** for invocation. If the
  condition isn't crisp, the skill's design probably has a deeper flaw
  -- the skill is doing too much or doesn't have a real role.
- Be **cost-justified, not over-aggressive**. Every skill load is tokens
  and a tool-call boundary; the trigger condition must justify that
  cost. A description that fires on topical adjacency ("...for any
  Python work...", "...whenever you read code...") violates the user's
  trust by burning tool calls without bringing value.
- Stay within the **length budget** (≤160 chars). A description that
  doesn't fit in 160 chars is summarizing capability, not naming a
  trigger.

**Exclusion**
A "Do NOT use for..." clause appended to `description`. Prevents
overtriggering on adjacent topics. Cited in the literature as the single
most important sentence in many skill descriptions because positive triggers
alone do not bound the activation surface.

**Rule**
A single MUST/MUST NOT statement in the body of a discipline-skill. A rule
without a counter is incomplete.

**Counter**
The rationalization rebuttal that closes a loophole on a rule. Lives next to
the rule it protects, typically in an `excuse → reality` table. A
discipline-skill needs a counter for every rationalization observed in
baseline testing.

**Step**
One ordered instruction in a procedure. Steps live in technique-skills and
in the procedural sections of script-bundled domain-skills.

**Checklist**
A copyable, tickable list the agent pastes into its response and ticks off
as it progresses. Used for procedures with more than three steps. Each
turn's unchecked items are what raise the bar against premature completion
claims.

**Example**
An input/output pair embedded in the skill body. Shows tone, format, and
detail level more clearly than prose can. Strong enough that style bias in
examples reproduces across all invocations — the example set should span
the variation the skill needs to support.

**Gotcha**
A documented failure mode observed in real runs. Often the most valuable
content in a mature reference-skill or technique-skill — happy paths Claude
can usually figure out; gotchas it cannot.

**Index**
A list of member skills with their triggers, used by container skills to
declare what they aggregate. The only convention specific to domain-skills.

---

### External binding

The runtime connection between a skill and an agent defined outside the
skill directory. The third and last category at the material level.

**Sub-agent binding**
A paired agent definition that auto-loads its companion skill on session
start. The convention is typically to name the agent after the skill it
wraps (e.g. an `unreal-kit-a` agent for a `/ue-python-api` domain-skill). The mechanism
by which a domain-skill becomes ambient context for a specialized agent.
Carried as the `agent-bundled` attribute on the skill.

---

## Method

The design vocabulary applied to material. Principles are the rules of
thumb that guide design choices; patterns are the named moves principles
justify. Both are referenced by name from skill-type contracts.

### Principles

Design rules of thumb that inform which patterns to apply when. The first
three are Robert C. Martin's package-cohesion principles applied to skill
documentation; the rest are framework principles, the last adapted from
Anthropic's best-practices doc. Patterns derive from principles; type
contracts compose patterns.

**Audience-Claude (skills are written for Claude, not users).**
Skills are runtime context for Claude, not documentation for humans.
Claude is the translator: when a user asks a question, Claude loads the
skill, picks the relevant data, and presents it to the user in the
user's natural language. This shapes authoring choices -- structured
data (YAML, tables, code-fenced blocks) is appropriate because Claude
consumes it; user-friendly prose is unnecessary because Claude
generates it on demand. The user is the audience of Claude's reply,
not of the skill itself.

*Form choice (not "everything is YAML"):* use YAML when the information
is structurally repetitive -- records with the same shape, lookup
tables, indexes, contract data, keyword-routed entries. Use prose when
the information is naturally narrative -- an identity sentence, an
orientation paragraph, a paragraph-length explanation that does not
decompose into discrete records. YAML for the sake of YAML obscures
content; the test is "does this structure aid Claude's comprehension
better than prose would?" If the answer is unclear, prose is the
default.

*Audit consequence: structural choices (YAML data blocks, dense tables,
condensed lists) are evaluated for whether they aid Claude's
comprehension, not for whether they read smoothly as prose.*
*Realized by: chat-term relevance hints (structured data carries the
user-language that should trigger it).*

**CRP — Common Reuse Principle (read-together).**
If a reader loads one section of a SKILL.md or reference file, they should
plausibly need the rest. When sections serve different reading tasks, split
them into separate files.
*Forcing readers through irrelevant content burns tokens and dilutes signal.*
*Realized by: progressive disclosure, domain-specific organization, conditional details.*

**CCP — Common Closure Principle (write-together).**
Content that changes for the same reason belongs in the same file. When a
system updates, only one file should need updating.
*A single conceptual change should be a single edit, not a hunt across files.*

**ADP — Acyclic Dependencies Principle (link-forward-only).**
References between files form a directed acyclic graph. No cycles.
*Cycles cause partial reads and ambiguous resolution order; a DAG guarantees the reader can always tell what comes first.*
*Realized by: progressive disclosure (one-hop-deep rule).*

**SSOT — Single Source of Truth.**
Every fact, term, or definition has exactly one canonical location. Other
places reference it by name; they do not redefine or duplicate.
*Drift between duplicates is the most common decay mode in skill documentation; one source means no drift.*
*Orientation-level summaries are not duplicates.* A short summary that
primes a reader to load the canonical reference is allowed when (a) the
summary names the reference and (b) the canonical wins on divergence. A
summary that has accumulated detail or examples beyond priming level has
decayed into duplication; collapse it to a pointer.

**Bottom-up composition.**
Atomic primitives are introduced before composed concepts that depend on
them. Within a document, sections appear in dependency order; within the
type system, atomic skill types (reference, pattern) come before composed
ones (technique, discipline, domain).
*The reader understands each section using only what they've already seen — this is also what makes ADP visible.*

**Context efficiency.**
Skills minimize their footprint in the context window. Two faces, both
required:
- *Structure* — defer optional material to reference files; keep scripts
  as executables (their code never enters context); pull content into the
  always-loaded SKILL.md body only when the agent needs it every time.
- *Writing* — every loaded paragraph justifies its tokens; assume Claude
  is capable; remove explanatory prose Claude doesn't need.

*Content the agent doesn't need wastes shared context that the user's task could use.*
*Realized by: progressive disclosure, domain-specific organization, conditional details, utility bundle (structure face); context budget (writing face).*

**Tool-call efficiency.**
Bundle repeated multi-call sequences into single script invocations.
Every tool call carries latency, context cost, and a turn boundary;
collapsing N calls into one is faster and cheaper.
*Audit by observing actual tool-call sequences in transcripts and identifying repeated multi-call patterns that could become a single script invocation.*
*Realized by: utility bundle.*

**Inference efficiency.**
Replace inference with deterministic scripts for operations the agent
performs repeatedly. Inference is expensive and non-deterministic;
scripts are cheap and predictable.
*Audit by reviewing inference-cost retrospectives and identifying operations that could move to scripts.*
*Realized by: utility bundle, template scaffold, self-correcting loop, plan-validate-execute.*

---

### Patterns

Named recurring moves authors apply to material. Patterns are the concrete
realization of principles — when a principle says "split for read-together
cohesion," patterns name specific ways to do that. Each pattern has a
defined name; contracts in the framework reference patterns by these names.
Patterns are grouped by purpose. Most are sourced from the Anthropic
best-practices doc; a few are named in the third-party 14-pattern synthesis
(Generative Programmer); the discipline group comes from obra/superpowers.

#### Discovery and selection

**Activation metadata**
The trigger and key terms packed into the `description` field. Third
person, "use when...", specific. The single signal Claude uses to select
which skill to load. *(Anthropic best-practices doc.)*

**Exclusion clause**
A "Do NOT use for..." appended to `description`. Bounds the activation
surface that activation metadata alone leaves open. *(Generative Programmer
14-pattern synthesis; cites Ruben Hassid.)*

**Chat-term relevance hints**
Keywords or short summaries embedded inside a skill's structured data
(YAML blocks, table rows, capability entries) that match user-language
phrasing, so Claude can route the user's words to the right data piece
without needing to read full reference text. The conditional-loading
block is the domain-skill version; in-record `keywords:` lists are the
same pattern applied per-entry. Without these hints, Claude has to
read body content top-to-bottom hunting for relevance; with them,
Claude jumps to the right slot directly.
*Fulfills: Audience-Claude, Tool-call efficiency, Inference efficiency.*

#### Context economy

**Context budget**
The discipline of making every paragraph in a SKILL.md justify its tokens.
Assume Claude is capable; remove explanatory prose Claude doesn't need.
*Fulfills: Concise is key. (Generative Programmer 14-pattern synthesis.)*

**Progressive disclosure**
Splitting content across the three load levels — L1 metadata always loaded,
L2 SKILL.md body loaded on trigger, L3 reference files loaded on demand.
SKILL.md should stay under 500 lines, and references should be one hop
deep, not nested. *Fulfills: CRP, ADP, Context efficiency. (Anthropic best-practices doc.)*

**Domain-specific organization**
Splitting reference content by sub-domain (e.g. `finance.md`, `sales.md`)
when sub-domains are mutually exclusive, so Claude reads only what's
relevant to the current task. *Fulfills: CRP, Context efficiency. (Anthropic best-practices doc.)*

**Conditional details**
Keeping basic content inline in SKILL.md and linking to advanced material
in reference files. *Fulfills: CRP, Context efficiency. (Anthropic best-practices doc.)*

#### Instruction calibration

**Control tuning**
Matching instruction freedom to task fragility. High freedom for open-field
work where multiple approaches are valid; low freedom for fragile sequences
where consistency is critical. Authors reliably over-constrain because
rigid feels safer. *(Anthropic best-practices doc.)*

**Explain-the-why**
Replacing imperatives ("MUST do X") with reasoning ("do X because Y") so
Claude can generalize the rule to unanticipated cases. *(Generative
Programmer 14-pattern synthesis.)*

**Template scaffold**
Embedding an output skeleton with placeholders that Claude fills. Strict
("ALWAYS use this template") for machine-parsed output; flexible ("sensible
default; adapt as needed") for human-reviewed work. *Fulfills: Inference efficiency. (Anthropic best-practices doc.)*

**In-skill examples**
Two or three input/output pairs that convey tone, format, and detail level.
Templates show the skeleton; examples show populated instances with style.
*(Anthropic best-practices doc.)*

**Known gotchas**
Concrete failure modes from real runs, documented alongside the happy path.
Often the most valuable content in a mature skill. *(Generative Programmer
14-pattern synthesis.)*

#### Workflow control

**Workflow checklist**
A copyable, tickable list provided for procedures with more than three
steps. The agent pastes the checklist into its response and ticks off items
as it works. *(Anthropic best-practices doc.)*

**Self-correcting loop**
The output → validate → fix → revalidate cycle, repeated until the
validator passes. The validator can be a script or a documented checklist.
*Fulfills: Inference efficiency. (Anthropic best-practices doc.)*

**Plan-validate-execute**
A three-step pattern for batch and destructive operations: produce a plan
as a structured artifact, validate the plan, then execute against it.
Catches errors before side effects rather than after. *Fulfills: Inference efficiency. (Anthropic best-practices doc.)*

#### Procedural composition

**Technique**
A self-contained how-to: an ordered sequence of steps for accomplishing a
defined goal, optionally with a bundled script and known gotchas. A
technique is the unit of action-oriented content in a skill. A skill may
contain one or more techniques — the technique-skill type does not imply
1-to-1.

**Capability**
A technique extended with structural metadata: a user-objective
description, an operation/tool reference, optional sub-cases, scope axes,
and a pointer to a reference section that owns full mechanics. Capabilities
surface action units as discrete, auditable entries with consistent
vocabulary and scope. Most commonly used inside domain-skills (where
multiple capabilities aggregate under one container), but applicable in any
skill that benefits from structured procedural surfaces — e.g. a
technique-skill exposing several variants of an action with shared scope
semantics. Capabilities are techniques+.

#### Executable code

**Utility bundle**
Purpose-built scripts shipped in a `scripts/` subdirectory of the skill,
used for deterministic operations rather than asking Claude to regenerate
the same helper each time. *Fulfills: Tool-call efficiency, Inference efficiency, Context efficiency. (Anthropic best-practices doc.)*

**Autonomy calibration**
Declaring `allowed-tools` in the SKILL.md frontmatter so the skill is
pre-approved to use only the tools it needs. Pre-approval is not the same
as a hard restriction; over-broad lists silently grant unintended autonomy.
*(Generative Programmer 14-pattern synthesis.)*

#### Discipline

**Adversarial pressure testing**
The RED → GREEN → REFACTOR cycle for discipline-skills. RED is the
baseline failure: a subagent without the skill violates the rule. GREEN is
the skill written so the same subagent now complies. REFACTOR closes
loopholes the agent finds under combined pressures (time + sunk cost +
fatigue). *(obra/superpowers.)*

**Rationalization counter table**
An explicit `excuse → reality` table that names every rationalization the
baseline agent produced and refutes it directly. *(obra/superpowers.)*

**Red flags list**
A short list of STOP signals the agent uses for self-checking — phrases
like "code before test", "just this once", "tests after achieve the same
purpose." *(obra/superpowers.)*

---

## Skill types

Contracts that compose material and method into auditable categories. Every
skill is one of these. The type names what kind of work a skill does; the
contract (in `skill-types-framework.md`) names which blocks and patterns it
must, may, and must not contain. The first four types are canonical from
`obra/superpowers/.../SKILL.md`; the fifth is a project addition.

The type name doesn't imply a 1-to-1 mapping between the skill and its
primary element. A pattern-skill may teach several related mental models;
a technique-skill may bundle several techniques; a discipline-skill may
enforce several rules. Reference-skills are already plural by name;
domain-skills are inherently plural as containers.

**Reference-skill**
A skill whose content is pure facts and lookup — API specs, syntax guides,
project conventions, vocabulary glossaries, error and symptom tables. No
procedure, no rule, no workflow. Atomic; composes from nothing. Canonical
from obra line 69.

**Pattern-skill**
A skill that teaches a mental model — a way of thinking about a class of
problem. Teaches recognition, not procedure. Atomic; peer of reference-skill.
Canonical from obra line 66.

**Technique-skill**
A skill whose primary content is one or more *techniques* (the procedural
pattern). Composes pattern + reference into procedure(s), and may bundle
scripts as canonical executable forms. Canonical from obra line 63. A
technique-skill invoked only by user slash command (rather than by LLM
auto-discovery) carries the `trigger: user-only` attribute; this replaces
what the project previously called `script-skill`.

**Discipline-skill**
A skill that enforces a rule under pressure. Wraps a target technique-skill
or pattern-skill with rules + counters and demands compliance even when
faster alternatives exist. Canonical from obra line 399 ("Discipline-Enforcing
Skills").

**Domain-skill**
A container skill that gathers leaf skills (references, patterns,
techniques, disciplines, scripts) for a knowledge area. Loading a
domain-skill primes the LLM with awareness of the whole set; specific members
load via their own triggers when relevant. Often paired with a sub-agent
that auto-loads the domain-skill on session start. Project term; no upstream
canonical reference. The only type the obra framework lacks.

---

## Orthogonal attributes

Properties a skill may carry independent of its type. A single skill can
carry several. None are canonical from upstream sources; all are project
labels.

**Trigger-model**
Whether a skill is invoked automatically by the LLM (`trigger: auto`, the
default and obra-canonical model) or only by the user via slash command
(`trigger: user-only`). The user-only attribute is the project's renaming
of what was previously a separate `script-skill` type — a slash-command
workflow is structurally a technique-skill with a different invocation
contract.

**Agent-bundled**
The attribute on a skill that is auto-loaded by a paired sub-agent on
session start. Most commonly seen on domain-skills paired with a domain-
specific agent that wraps the skill's vocabulary and member set. Example:
`/ue-python-api` (unreal-kit domain-skill).

**Harness-targeted**
The attribute on a skill that operates on the Claude Code harness or agent
itself rather than on project work. Harness-targeted skills change their
audit criterion: success is verified by checking that the harness reflects
the change, not by running a project task. Typical examples: `/bootstrap`
(interpreting SessionStart bootstrap messages); `/cache-report` (displaying
session cache metrics); skills that audit permission rules in settings.

**Integration**
The attribute on a skill that talks to a third-party system. Typical
examples: `/local-code-review` (submits to Perforce and returns review comments);
`/bootstrap` (manages plugin marketplaces and remote dependencies); skills
syncing files to a remote git host.

**Bootstrap**
The attribute on a skill that performs one-time setup. Typical examples:
`/bootstrap` (initializes plugin dependencies and configuration on session start);
a skill that scans recent transcripts to seed an allowlist.

**Scheduled / autonomous**
The attribute on a skill designed to run via `/loop` or `/schedule` rather
than through interactive use.

**Script-bundling**
The attribute on a skill that ships executable resources (Python, shell)
alongside its markdown. Common for technique-skills, the procedural
portions of domain-skills, and any skill applying the utility-bundle
pattern.

---

## Sources

External works cited inline. Italic citations elsewhere in this glossary
refer to entries in this list.

- **Anthropic best-practices doc** — [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), Anthropic Claude Docs.
- **Generative Programmer 14-pattern synthesis** — [Skill Authoring Patterns from Anthropic's Best Practices](https://generativeprogrammer.com/p/skill-authoring-patterns-from-anthropics). Cites Ruben Hassid for the exclusion-clause pattern.
- **obra/superpowers** — [skills/writing-skills/SKILL.md](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md), Jesse Vincent. Source of the four canonical skill type names (reference, pattern, technique, discipline-enforcing) and the discipline patterns (adversarial pressure testing, rationalization counter table, red flags list).
- **Robert C. Martin** — package-cohesion principles (CRP, CCP, ADP) from *Agile Software Development: Principles, Patterns, and Practices* (2002), applied here to skill documentation.
