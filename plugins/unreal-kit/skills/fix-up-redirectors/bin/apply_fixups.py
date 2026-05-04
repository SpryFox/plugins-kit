"""Phase 3 facade: apply fixups for the safe set in a fresh CL.

Runs inside Unreal as a commandlet. Reads SAFE_JSON env var. Optionally
reads CL_DESC_SUFFIX env var (e.g. '[Mix, Tool]') to append a project-specific
tag to the CL description.

Flow:

  1. Guard against duplicate "Fix up redirectors" pending CLs (auto-detects
     P4USER from `p4 info` if not in env).
  2. Create a fresh pending CL.
  3. `p4 edit` only the non-redirector REFERENCER files into the CL. The
     redirector .uasset files are not edited - they will be deleted instead.
  4. UE: load every referencer asset and force-save it. UE's Linker resolves
     redirectors at load time; force-saving rewrites the package's import
     table to reference the redirector's target directly, severing the link.
     Soft references that were not auto-resolved are also rewritten via
     `rename_referencing_soft_object_paths` after the packages are loaded.
  5. `p4 delete` the redirector .uasset files into the same CL. This opens
     them for delete and removes them from the workspace.
  6. Save a manifest.

UE5.x note: `unreal.AssetTools.fixup_referencers` does NOT exist in current
Python bindings. Steps 3-5 are the supported substitute.
"""
import os
import sys

sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/lib'))
sys.path.insert(0, os.path.expanduser('~/.claude/plugins/data/plugins-kit/unreal-kit/github/unreal-pip'))
from bootstrap import ensure_dependencies
ensure_dependencies()

# Restore registry-canonical PATH before p4 subprocess fan-out (see
# unreal-kit/lib/path_repair.py). Defense-in-depth — even though UE
# commandlets rarely trip cmd.exe overflow, the cost is negligible.
from path_repair import repair_path
repair_path()

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
import unreal
from p4cli import (
    create_pending_cl, delete_files, edit_files, get_p4_user, reopen_files,
    run_p4, run_p4_or_die,
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

# 1) Guard: refuse if a "Fix up redirectors" CL is already pending for this user.
if not FORCE_NEW_CL:
    p4_user = get_p4_user()
    if not p4_user:
        sys.stderr.write(
            "[apply_fixups] WARN: Could not resolve P4USER (env or `p4 info`). "
            "Skipping the existing-CL guard.\n"
        )
    else:
        existing = run_p4_or_die(['changes', '-s', 'pending', '-l', '-u', p4_user])
        for chunk in existing.split('Change '):
            if 'Fix up redirectors' in chunk:
                cl_num = chunk.split(' ', 1)[0].strip()
                fail(
                    f"Pending CL {cl_num} already starts with 'Fix up redirectors'. "
                    f"Submit/revert it first, or pass --force-new-cl."
                )

# 2) Build the file sets.
#    - redirector_files: every redirector .uasset (these will be DELETED).
#    - referencer_pkgs / referencer_files: union of all referencers,
#      MINUS any package that is itself a redirector in this safe set
#      (those will be deleted, not re-saved).
redirector_pkgs = {r['pkg'] for r in records}
redirector_files = [r['file'] for r in records if r.get('file')]

referencer_pkgs = set()
referencer_files = set()
for r in records:
    for ref_pkg in (r.get('referencer_pkgs') or []):
        if ref_pkg in redirector_pkgs:
            continue
        referencer_pkgs.add(ref_pkg)
    for ref_file in (r.get('referencer_files') or []):
        referencer_files.add(ref_file)
# Drop referencer files that are themselves redirector files.
referencer_files -= set(redirector_files)
referencer_files = sorted(referencer_files)

print(f"Redirectors to delete: {len(redirector_files)}")
print(f"Non-redirector referencers to rewrite: {len(referencer_pkgs)} pkgs / "
      f"{len(referencer_files)} files")

# 3) Create the CL.
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

# 4) p4 edit only the non-redirector referencer files (so UE can re-save them).
if referencer_files:
    edit_files(cl_num, referencer_files)
    print(f"Opened {len(referencer_files)} referencer file(s) for edit in CL {cl_num}.")

# 5) UE: load each referencer (resolves redirectors at link time), rewrite
#    soft references via the supported API, then force-save so the package
#    import table is rewritten to reference the target directly.
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()


def _soft_object_path(pkg_path):
    asset_name = pkg_path.rsplit('/', 1)[-1]
    return unreal.SoftObjectPath(f"{pkg_path}.{asset_name}")


loaded_referencers = []
load_failures = []
for pkg in sorted(referencer_pkgs):
    asset = unreal.EditorAssetLibrary.load_asset(pkg)
    if asset is None:
        load_failures.append(pkg)
    else:
        loaded_referencers.append(pkg)
print(f"Loaded {len(loaded_referencers)} referencer asset(s) "
      f"({len(load_failures)} failed to load)")

# Soft-reference rewrite (only meaningful when there are loaded packages).
redirector_map = {}
for r in records:
    target = r.get('target_pkg')
    if target and r.get('target_exists'):
        redirector_map[_soft_object_path(r['pkg'])] = _soft_object_path(target)
if loaded_referencers and redirector_map:
    pkg_names = unreal.Array(unreal.Name)
    for p in loaded_referencers:
        pkg_names.append(unreal.Name(p))
    asset_tools.rename_referencing_soft_object_paths(pkg_names, redirector_map)
    print("Rewrote soft references.")

saved = 0
save_failures = []
for pkg in loaded_referencers:
    asset = unreal.EditorAssetLibrary.load_asset(pkg)
    if asset is None or not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        save_failures.append(pkg)
    else:
        saved += 1
print(f"Force-saved {saved} referencer package(s) "
      f"({len(save_failures)} failures)")

# 6) Delete each redirector via UE, then have P4 record the deletes.
#    `EditorAssetLibrary.delete_asset` unloads the package from memory and
#    removes the local .uasset, releasing the Windows file handle that UE
#    would otherwise be holding. Without this step, `p4 delete`'s internal
#    unlink fights UE for the file lock and the batch fails partway.
ue_deleted = 0
ue_delete_failures = []
for r in records:
    pkg = r['pkg']
    try:
        if unreal.EditorAssetLibrary.does_asset_exist(pkg):
            if unreal.EditorAssetLibrary.delete_asset(pkg):
                ue_deleted += 1
                continue
        ue_delete_failures.append(pkg)
    except Exception as exc:
        ue_delete_failures.append(f"{pkg}: {exc}")
print(f"UE-deleted {ue_deleted} redirector asset(s) "
      f"({len(ue_delete_failures)} failures)")

# Force a GC pass so any lingering handles on package objects are released
# before P4 tries to record the delete.
try:
    unreal.SystemLibrary.collect_garbage(0)
except Exception:
    pass

# UE's source-control plugin auto-opens the deletes into the default CL.
# `p4 delete -c <CL>` does NOT move already-opened files - it just no-ops.
# Use `p4 reopen -c <CL>` to herd them into our pending CL, falling back
# to `p4 delete -c <CL>` for any that source control didn't auto-open.
delete_failures = []
if redirector_files:
    rc, out, _err = run_p4(['-x', '-', 'fstat', '-T', 'depotFile,action,change'],
                           stdin='\n'.join(redirector_files))
    auto_opened = []
    not_opened = []
    cur_path = None
    cur_action = None
    cur_change = None
    if rc == 0:
        for line in out.splitlines():
            line = line.strip()
            if not line:
                if cur_path and cur_action == 'delete':
                    auto_opened.append(cur_path)
                elif cur_path and cur_action is None:
                    not_opened.append(cur_path)
                cur_path = cur_action = cur_change = None
            elif line.startswith('... depotFile '):
                cur_path = line[len('... depotFile '):]
            elif line.startswith('... action '):
                cur_action = line[len('... action '):]
            elif line.startswith('... change '):
                cur_change = line[len('... change '):]
        if cur_path and cur_action == 'delete':
            auto_opened.append(cur_path)
        elif cur_path and cur_action is None:
            not_opened.append(cur_path)

    if auto_opened:
        try:
            reopen_files(cl_num, auto_opened)
            print(f"Reopened {len(auto_opened)} UE-auto-deleted redirector(s) into CL {cl_num}.")
        except SystemExit:
            delete_failures.extend(auto_opened)
            sys.stderr.write("[apply_fixups] WARN: p4 reopen batch failed; see error above.\n")
    if not_opened:
        try:
            delete_files(cl_num, not_opened)
            print(f"Opened {len(not_opened)} redirector(s) for delete in CL {cl_num}.")
        except SystemExit:
            delete_failures.extend(not_opened)
            sys.stderr.write("[apply_fixups] WARN: p4 delete batch failed; see error above.\n")

# 7) Manifest.
manifest = {
    'cl': cl_num,
    'scope': scope,
    'redirectors_deleted': len(redirector_files) - len(delete_failures),
    'referencers_saved': saved,
    'referencer_save_failures': save_failures,
    'redirector_delete_failures': delete_failures,
    'load_failures': load_failures,
}
manifest_path = os.path.join(
    str(unreal.Paths.project_dir()), 'Saved', 'PythonOutput',
    f'redirectors_apply_{cl_num}.yaml',
)
save_apply_manifest(manifest_path, manifest)

print()
print(f"Done. CL {cl_num}: deleted {manifest['redirectors_deleted']} redirectors, "
      f"saved {saved} referencers.")
print(f"Manifest: {manifest_path}")
