// claude-md-audit — DETECT workflow (before-Q&A phase).
//
// Fan-out detection + classification, one lane per target CLAUDE.md file. Each
// lane reads the file (and its parent, for child role), loads the SINGLE
// self-contained audit-criteria doc, applies the role-to-criteria map,
// optionally runs the mechanical schema validator, and classifies every finding
// into the taxonomy + a remediation bucket. Cache efficiency: each fan-out lane
// is an isolated context whose prompt prefix is NOT shared across siblings (the
// Workflow tool re-creates per-lane cache beyond a fixed harness shell), so the
// lane loads exactly ONE criteria doc -- the upstream content-allocation
// framework is the derivation, not the operative rules, and is intentionally not
// read here. Pure detection — NO file is modified here (the skill's
// `audit_then_self_remediate` anti-pattern keeps detection and remediation in
// separate phases). Returns structured per-file findings for the main loop to
// render and dispatch.
//
// Invoked by the claude-md-audit SKILL.md only when auditing 2+ files (the
// multi-file threshold that equalizes the Workflow tool's per-run overhead).
// Single-file audits run inline in the main loop.
//
// args = {
//   files: [ { path: string, role: "root"|"ancestor"|"child"|"local",
//              parentPath: string|null } ],
//   refs:  { criteria: <abs path to references/audit-criteria.md>,
//            pluginRoot: <abs path to plugins/skills-kit (parent of skills_kit_lib)>,
//            venvPython: <abs path to skills-kit venv python> }
// NOTE: contentAllocation is no longer consumed by lanes (dropped for cache
// efficiency); SKILL.md need not pass it. A stale ref is harmless (unused).
// }
// The schema validator is invoked as a module:
//   (cd <pluginRoot> && <venvPython> -m skills_kit_lib.audit <file> --json)

export const meta = {
  name: 'claude-md-audit-detect',
  description: 'Fan-out CLAUDE.md audit: read + apply CCP/CRP/ADP criteria + schema-validate + classify, one lane per file (detection only, no edits)',
  phases: [{ title: 'Audit', detail: 'one lane per CLAUDE.md file' }],
}

const FILE_FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    path: { type: 'string' },
    role: { type: 'string', enum: ['root', 'ancestor', 'child', 'local'] },
    lines: { type: 'integer' },
    approx_tokens: { type: 'integer' },
    has_schema_block: { type: 'boolean' },
    parent_available: { type: 'boolean', description: 'true if a parent CLAUDE.md was read (child role); false/irrelevant otherwise' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          group: { type: 'string', enum: ['CCP', 'CRP', 'ADP', 'Hygiene', 'Schema'] },
          severity: { type: 'string', enum: ['PASS', 'FAIL', 'INFO', 'JUDGMENT'] },
          criterion: { type: 'string', description: 'criterion id or short name, e.g. ccp_cross_file_duplication' },
          message: { type: 'string' },
          line: { type: ['integer', 'null'], description: 'line number in the file, or null' },
          taxonomy: { type: 'string', description: 'taxonomy id A-G or K; "none" for PASS/INFO/JUDGMENT that need no remediation' },
          bucket: { type: 'string', enum: ['AUTO', 'DISCUSS', 'SPECIAL', 'NONE'] },
          remediation: { type: 'string', description: 'concrete proposed remediation for AUTO/DISCUSS/SPECIAL; empty for NONE' },
        },
        required: ['group', 'severity', 'criterion', 'message', 'line', 'taxonomy', 'bucket', 'remediation'],
      },
    },
    verdict: { type: 'string', enum: ['COMPLIANT', 'NON-COMPLIANT'] },
  },
  required: ['path', 'role', 'lines', 'approx_tokens', 'has_schema_block', 'parent_available', 'findings', 'verdict'],
}

// args may arrive as an object or as a JSON string depending on how the
// invoker passes it; normalize to an object.
let input = args
if (typeof input === 'string') {
  try { input = JSON.parse(input) } catch (_) { input = null }
}
if (!input || !Array.isArray(input.files) || input.files.length === 0) {
  throw new Error('detect.js requires args.files = [{path, role, parentPath}]')
}
const refs = input.refs || {}

function lanePrompt(f) {
  const parentClause = f.role === 'child' && f.parentPath
    ? `This is a CHILD file. Also Read its parent CLAUDE.md at ${f.parentPath} so you can run the CCP cross-file duplication check (a rule restated from the parent is a FAIL, taxonomy B, bucket AUTO).`
    : `No parent read is required for role=${f.role}.`

  const schemaClause = refs.pluginRoot && refs.venvPython
    ? `If the file body contains a \`claude_md:\` YAML contract block, run the mechanical schema validator via Bash (it is a package module, so cd into the plugin root first):\n    (cd "${refs.pluginRoot}" && "${refs.venvPython}" -m skills_kit_lib.audit "${f.path}" --json)\nand merge its results as Schema-group findings (validation failure on a non-optional field = FAIL, taxonomy E). If the validator is unavailable or errors, emit one Schema finding with severity JUDGMENT and message "schema validator unavailable" and continue. If there is no \`claude_md:\` block, skip the Schema group entirely (do NOT fail a file for not declaring a contract).`
    : `Schema validator path was not provided; if the file has a \`claude_md:\` block, emit one Schema finding with severity JUDGMENT noting the validator was unavailable.`

  return `You are ONE lane of a CLAUDE.md audit. Audit exactly one file and return structured findings. This is DETECTION ONLY — do not modify any file.

Target: ${f.path}
Role:   ${f.role}

Steps:
1. Read the target file. Count its lines and estimate tokens (~chars/4).
2. Read the audit criteria and role-to-criteria map at ${refs.criteria}. This file is self-contained: every testable rule is stated together with the CCP / CRP / ADP principle it derives from. Do NOT load any other framework document -- everything needed to classify is in this one file. (Principle recap so you can apply them without re-derivation: CCP = content that changes for the same reason belongs together; a rule duplicated across scopes is a FAIL. CRP = a fact lives in the smallest scope whose readers all need it. ADP = cross-file references must resolve and run downward in load order; a broken or stale reference is a FAIL.)
3. ${parentClause}
4. Apply the criteria that the role-to-criteria map says apply to role=${f.role}. Produce findings tagged with group (CCP / CRP / ADP / Hygiene) and severity (PASS / FAIL / INFO / JUDGMENT). For role=local, only the D-group / local criteria apply (skip Hygiene and ADP per the map).
5. ${schemaClause}
6. Classify EVERY non-PASS finding into a taxonomy id (A-G, or K if nothing fits) and a remediation bucket:
     - AUTO    = mechanical, safe to auto-apply (e.g. B: delete restated parent rule)
     - DISCUSS = needs a user decision (A, C, D, E-authorial, F, G)
     - SPECIAL = K, unclassified
   PASS / INFO / JUDGMENT findings that need no remediation get taxonomy "none" and bucket "NONE".
   For each AUTO/DISCUSS/SPECIAL finding write a concrete \`remediation\` (what edit you propose, with line refs).
7. Verdict: NON-COMPLIANT if ANY finding has severity FAIL; otherwise COMPLIANT. INFO/JUDGMENT never gate.

Idempotency matters: apply the fixed criteria and taxonomy deterministically. Do not invent findings; report only what the criteria actually surface. Return the structured object.`
}

phase('Audit')
const perFile = await parallel(input.files.map((f) => () =>
  agent(lanePrompt(f), {
    label: `audit:${f.path.split(/[\\/]/).pop()}`,
    phase: 'Audit',
    schema: FILE_FINDINGS_SCHEMA,
  }).then((r) => ({ ...r, path: f.path, role: f.role }))
))

const results = perFile.filter(Boolean)
const totals = results.reduce((acc, r) => {
  for (const fnd of r.findings) {
    if (fnd.bucket === 'AUTO') acc.auto++
    else if (fnd.bucket === 'DISCUSS') acc.discuss++
    else if (fnd.bucket === 'SPECIAL') acc.special++
    if (fnd.severity === 'FAIL') acc.fail++
  }
  if (r.verdict === 'NON-COMPLIANT') acc.nonCompliant++
  return acc
}, { auto: 0, discuss: 0, special: 0, fail: 0, nonCompliant: 0 })

log(`Audited ${results.length}/${input.files.length} files — ${totals.nonCompliant} NON-COMPLIANT, ${totals.fail} FAIL findings; buckets AUTO=${totals.auto} DISCUSS=${totals.discuss} SPECIAL=${totals.special}`)

return { perFile: results, totals }
