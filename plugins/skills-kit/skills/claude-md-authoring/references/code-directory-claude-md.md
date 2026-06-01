# Authoring a CLAUDE.md inside a code / YAML / CSV directory

Load this when the target CLAUDE.md sits **inside (or describes) a directory of code, YAML, or CSV** — a per-directory review-notes file, not a project-root or docs CLAUDE.md. (Detection mirrors the audit's Level-1 trigger: code/data siblings, or review-claim/shape markers, and no `claude_md:` block / no sibling SKILL.md.) For a root or docs CLAUDE.md, ignore this doc and use the normal claude_md craft.

This doc owns the **code-directory craft**. Placement (which CLAUDE.md a fact belongs in) still defers to `cohesion-principles`; content form (YAML vs prose) still defers to `content-authoring`. What follows is *what is worth writing* and *how to anchor it* so it survives.

## The north star

The file will be read by a code-review agent reviewing a diff in this directory. **A section earns its place only if it makes that agent catch something a senior teammate catches and a generic reviewer misses.** You are an experienced tech lead writing the onboarding notes you wish you'd had — not documentation. Every section costs attention budget; spend it on what goes wrong, not on what's obvious.

## Step 1 — pick the shape (mixing is allowed)

A directory whose review surface genuinely spans several concerns may **mix** shapes in one file (architecture preamble + gotcha list + boundary rule). Don't mix gratuitously, but don't split a cohesive file just to keep one shape.

- **Shape A — gotcha-per-section** (source code). Each `##` heading is a claim; the body gives an anchor + a why + a do-instead.
- **Shape B — purpose + Schema/Files + Review Checks** (YAML/CSV data). One-line purpose, an *annotated* structural section, then a `## Review Checks` section — that section is the payload, not the prose.
- **Shape C — boundary / ownership** (directory-level). The heading is a boundary statement; the body says what lives here vs. not, plus safety rails and ordering invariants. Often a `## Children` index with cross-cutting blast-radius notes.
- **Shape D — architecture / pointer-hub**. Headings are labels; a descriptive lead paragraph is fine. Attach the do-instead to the specific invariant ("do not diverge from the binary layout"), not the topic heading. Pointer-hub files mostly say "this rule is universal; payload lives in `<SSOT>`; here is the one local delta."

## Step 2 — write only the high-value kinds

Ask which of these are present **and silent** in this directory. Write those; skip the rest.

- **Shape A:** god-object/don't-add-here · deliberate hack/workaround (and *don't simplify*) · diff-invisible perf trap (O(N), per-tick) · lifetime/ownership hazard (raw `this` capture, must-outlive) · type-safety bypass (*don't copy*) · dead/misleading code · build-flag-dependent behavior · lifecycle-method contract (what goes in which method) · "use the helper, not inline".
- **Shape B:** cross-config referential integrity, naming the **silent-failure mode** (*"mismatches are silent at build time"*) · rename/removal blast radius (*"search for usages first"*) · "not just config review" escalation · secrets hygiene · asset/external-path validity · **append-only data-ledger** (order-immutable, sentinel value, "removing an entry corrupts save data").
- **Shape C:** allowed/FORBIDDEN safety rails · gitignored-by-design / tracked-file-is-a-leak · vendored subtree ("review provenance not bytes") · deploy/migration ordering invariant · children-index blast radius · pointer to a universal rule.
- **Shape D:** architecture invariant (named pattern) · pointer-hub (point, don't restate) · **external-contract**.

### Two idioms the generic "anchor + why + do-instead" rule doesn't cover

- **External-contract:** when the other side of a contract lives in another repo (a C++ client consuming this REST API; wire constants that must match the gameserver), the complete claim is **the local constant + "the other side lives in `<repo>`; verify by hand."** This is finished, not a defective bare prohibition — don't force a do-instead onto it.
- **Negative-existence (assert-absence):** for secrets dirs and forbidden targets, the claim shape is **assert-absence + the detection-trigger**: "this is gitignored / does not exist in a clean checkout; **a tracked file here is the finding.**" The "do-instead" is the detection rule itself.

## Step 3 — anchoring discipline (this is what makes claims survive)

- **Prefer a symbol anchor over a line anchor.** Line numbers rot fast (in our corpus, 3 of 4 sampled line anchors were already 5–190 lines off). **Drop the line number entirely unless the gotcha is sub-function**; when a line genuinely helps, mark it best-effort (`~2204-2215`) *and* name the enclosing symbol so it's recoverable after drift. If you must cite a volatile line, give the recovery hint ("run `grep -n '# NOTE:'` first").
- **Counted magnitudes are illustrative, not contractual.** "7200-line god object" communicates the kind; don't sweat the exact number — but write the claim so it stays true even as the number drifts (the *kind* is the claim, the number is color).
- **Every prohibitive claim states the why and a do-instead** ("don't add to it → put new behavior in a UActorComponent"). A bare prohibition is a defect — *except* the external-contract and negative-existence idioms above, which are complete as written.

## Step 4 — path discipline for cross-references

- **Near-sibling references → relative** (`../Cohorts/`, `../BuildingTileset/file.yaml`).
- **Cross-subtree universal-rule pointers → repo-root-absolute with a leading slash** (`/docs/code-review/...`, `/kubernetes/CLAUDE.md`). This is more robust than fragile `../../../` chains and is a deliberate, good convention.
- **Never** tree-absolute *without* a leading slash (`GameConfigs/Real/Items/`) — that is the single most common broken-reference pattern in our corpus; it resolves from nowhere.

## Step 5 — run every section through the value gate before writing it

Lead with silent-failure and blast-radius content; order by the §north-star ranking. **Do not write** a section that:

- a compiler / linter / type-checker / CI already enforces;
- restates a language or framework default, or generic programming advice the model already knows;
- repeats a rule already stated in an ancestor CLAUDE.md (state it once, at the right scope);
- is a **bare** directory inventory or file listing for its own sake;
- is an empty heading with no claim;
- restates a self-describing schema as the file's substance.

(But an *annotated* `## Files`/`## Schema` block — each entry carrying a constraint — IS payload; keep it. A constraint catalog that points to its SSOT, a safety-rail command cheatsheet, and a topology/ownership table are all keepers, not inventories.)

## Negative space (anti-patterns to avoid, named)

No bare directory inventories · no empty CLAUDE.md (a heading with no claim) · no schema restatement as substance · no line-only anchors lacking a symbol · no tree-absolute-without-leading-slash sibling paths · no language defaults or linter-enforced style · no do-instead-less prohibition (except the external-contract / negative-existence idioms).

## Cross-references

- **Where a fact lives** — `cohesion-principles` (placement: CCP / CRP / ADP).
- **What shape a fact takes** — `content-authoring` (md-authoring reference).
- **The audit counterpart** — `claude-md-audit:references/code-dir-insight-filter.md` validates exactly these claims (fidelity + value); authoring to this doc is what keeps that audit green.
