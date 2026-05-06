# Perforce CLI Gotchas

Edge cases and silent failure modes encountered when parsing `p4` CLI output across plugins-kit code (notably p4-kit, and unreal-kit's fix-up-redirectors). Add new entries when one bites; this is the catch-all so individual plugins don't have to re-discover the same traps.

## `p4 -F %userName% info` returns empty stdout (silent failure)

The `%userName%` format variable is supported by `p4 user -o` (where `userName` is a documented tagged field) but **NOT** by `p4 info`. Calling `p4 -F %userName% info` exits 0 with empty stdout on at least one production Perforce server (P4D/LINUX26X86_64/2025.1).

Robust pattern: parse plain-text `p4 info` output for `User name: <name>`:

```python
rc, out, _err = run_p4(['info'])
if rc != 0:
    return ''
for line in out.splitlines():
    if line.startswith('User name:'):
        return line.split(':', 1)[1].strip()
return ''
```

The empty-stdout failure is silent -- the calling code sees `rc=0`, treats the empty result as authoritative, and falls through to whatever default it has for "no user". In `unreal-kit/skills/fix-up-redirectors/lib/p4cli.py` this caused the existing-CL guard in `apply_fixups.py` to silently skip, allowing duplicate pending fix-up CLs to be created on a re-run.

**Generic lesson:** `p4 -F` is for *tagged* output formats. Verify each field exists in tagged output via `p4 -ztag <command>` before relying on it. If a tagged field doesn't exist for the command in question, fall back to plain-text parsing -- don't assume `-F` will degrade gracefully.

Surfaced 2026-05-05; fixed in unreal-kit 0.9.4.
