"""Phase 3 facade: apply fixups for the safe set in a fresh CL.

Runs inside Unreal as a commandlet. Reads SAFE_JSON env var. Optionally
reads CL_DESC_SUFFIX env var (e.g. '[Mix, Tool]') to append a project-specific
tag to the CL description.

Aborts on any P4 failure or CL-content mismatch before calling fixup_referencers.
"""
import os, sys

sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/lib'))
sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/github/unreal-pip'))
from bootstrap import ensure_dependencies
ensure_dependencies()

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
import unreal
from p4cli import (
    create_pending_cl, edit_files, get_opened_in_cl, run_p4, run_p4_or_die, where_batch,
)
from redirector_record import load_safe_set, save_apply_manifest


def fail(msg):
    sys.stderr.write(f"[apply_fixups] FAIL: {msg}\n")
    sys.exit(1)


SAFE_JSON = os.environ.get('SAFE_JSON')
CL_DESC_SUFFIX = os.environ.get('CL_DESC_SUFFIX', '').strip()
FORCE_NEW_CL = '--force-new-cl' in sys.argv

if not SAFE_JSON or not os.path.isfile(SAFE_JSON):
    fail(f"SAFE_JSON env var not set or file missing: {SAFE_JSON!r}")

safe = load_safe_set(SAFE_JSON)
scope = safe.get('scope', '/Game')
records = safe.get('redirectors', [])
if not records:
    print("Nothing safe to fix - aborting.")
    sys.exit(0)

# Refuse if a "Fix up redirectors" CL is already pending (unless --force-new-cl).
if not FORCE_NEW_CL:
    existing = run_p4_or_die(['changes', '-s', 'pending', '-l', '-u', os.environ.get('P4USER', '')])
    for chunk in existing.split('Change '):
        if 'Fix up redirectors' in chunk:
            cl_num = chunk.split(' ', 1)[0].strip()
            fail(f"Pending CL {cl_num} already starts with 'Fix up redirectors'. "
                 f"Submit/revert it first, or pass --force-new-cl.")

# Union the file set: every redirector + every referencer.
files = []
seen_files = set()
for r in records:
    for path in [r.get('file')] + list(r.get('referencer_files', []) or []):
        if path and path not in seen_files:
            seen_files.add(path)
            files.append(path)

print(f"Will edit {len(files)} files for {len(records)} redirectors in scope {scope}")

# 1) Create the CL.
title = f"Fix up redirectors: {len(records)} assets in {scope}"
if CL_DESC_SUFFIX:
    title = f"{title} {CL_DESC_SUFFIX}"
description = (
    f"{title}\n\n"
    "Automated cleanup via /fix-up-redirectors. Rewrites referencers to point at "
    "redirector targets and deletes the redirector .uasset files."
)
cl_num = create_pending_cl(description, client=os.environ.get('P4CLIENT'))
print(f"Created CL {cl_num}")

# 2) p4 edit the union into that CL.
edit_files(cl_num, files)

# 3) Validate: opened-in-CL set must equal expected depot-path set.
opened_depots = get_opened_in_cl(cl_num)
expected_depots = where_batch(files)
missing = expected_depots - opened_depots
extra = opened_depots - expected_depots
if missing or extra:
    fail(f"CL {cl_num} validation failed.\n  missing: {len(missing)}\n  extra: {len(extra)}\n"
         f"  missing samples: {list(missing)[:5]}\n  extra samples: {list(extra)[:5]}")
print(f"CL {cl_num} validated: {len(opened_depots)} files match expected set.")

# 4) Run fixup_referencers in UE.
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
loaded = []
load_failures = []
for r in records:
    asset = unreal.EditorAssetLibrary.load_asset(r['pkg'])
    if asset is None:
        load_failures.append(r['pkg'])
    else:
        loaded.append(asset)
print(f"Loaded {len(loaded)} redirector assets ({len(load_failures)} failed to load)")

if loaded:
    asset_tools.fixup_referencers(loaded, checkout_dialog_prompt=False)

# 5) Reconcile deletes.
redirector_files = [r['file'] for r in records if r.get('file')]
if redirector_files:
    rc, _out, err = run_p4(['-x', '-', 'reconcile', '-c', cl_num], stdin='\n'.join(redirector_files))
    if rc != 0:
        sys.stderr.write(f"[apply_fixups] WARN: p4 reconcile returned {rc}: {err}\n")

# 6) Manifest.
manifest = {
    'cl': cl_num, 'scope': scope,
    'redirectors_fixed': len(loaded),
    'load_failures': load_failures,
    'files_edited': len(files),
}
manifest_path = os.path.join(str(unreal.Paths.project_dir()), 'Saved', 'PythonOutput',
                             f'redirectors_apply_{cl_num}.yaml')
save_apply_manifest(manifest_path, manifest)

print()
print(f"Done. CL {cl_num}: fixed {len(loaded)} redirectors, edited {len(files)} files.")
print(f"Manifest: {manifest_path}")
