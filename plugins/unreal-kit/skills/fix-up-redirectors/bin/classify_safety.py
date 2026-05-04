"""Phase 2 facade: classify each redirector as safe-to-fix or blocked.

Host-side. Reads phase-1 YAML, runs `p4 opened -a` once, and emits:
- safe-set JSON for phase 3
- report JSON for the skill prompt
"""
import argparse
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
# Plugin-level lib (for path_repair) — bin/ -> skill/ -> skills/ -> unreal-kit/lib
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lib')))
from path_repair import repair_path
repair_path()

from p4cli import get_opened_map, get_workspace_mapping, local_to_depot
from redirector_record import load_discovery, save_safe_set, save_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--discovery', required=True, help='Phase 1 YAML output')
    ap.add_argument('--out-safe', required=True, help='Where to write the safe-set JSON for phase 3')
    ap.add_argument('--out-report', required=True, help='Where to write the report JSON')
    args = ap.parse_args()

    discovery = load_discovery(args.discovery)
    scope = discovery.get('scope', '/Game')
    redirectors = discovery.get('redirectors', [])

    depot_root, local_root = get_workspace_mapping()
    opened = get_opened_map()

    safe = []
    blocked = []
    broken = []
    non_writable = []
    safe_with_level = 0
    blocked_by_user = Counter()
    blocked_changes_by_user = defaultdict(set)

    for r in redirectors:
        if not r.get('target_exists'):
            broken.append(r)
            continue
        if r.get('has_unresolvable_referencer'):
            non_writable.append(r)
            continue

        all_files = [r['file']] + list(r.get('referencer_files', []))
        blockers = []
        for local_path in all_files:
            if not local_path:
                continue
            depot = local_to_depot(local_path, depot_root, local_root)
            if not depot:
                blockers.append({'file': local_path, 'reason': 'not_in_workspace'})
                continue
            for entry in opened.get(depot.lower(), []):
                blockers.append({
                    'file': local_path, 'depot': depot,
                    'user': entry['user'], 'change': entry['change'],
                })

        if blockers:
            r['blockers'] = blockers
            blocked.append(r)
            for b in blockers:
                u = b.get('user')
                if u:
                    blocked_by_user[u] += 1
                    blocked_changes_by_user[u].add(str(b.get('change', '')))
        else:
            safe.append(r)
            if r.get('has_level_referencer'):
                safe_with_level += 1

    report = {
        'scope': scope,
        'total': len(redirectors),
        'counts': {
            'safe': len(safe),
            'safe_touching_levels': safe_with_level,
            'blocked': len(blocked),
            'broken': len(broken),
            'non_writable': len(non_writable),
        },
        'blocked_by_user': [
            {'user': user, 'count': count, 'changes': sorted(blocked_changes_by_user[user])}
            for user, count in blocked_by_user.most_common()
        ],
        'broken_samples': [r['pkg'] for r in broken[:20]],
    }

    save_safe_set(args.out_safe, scope, safe)
    save_report(args.out_report, report)

    print(f"Scope: {scope}")
    print(f"Total: {len(redirectors)}")
    print(f"  safe to fix:      {len(safe)}" + (f"  ({safe_with_level} touch levels)" if safe_with_level else ""))
    print(f"  blocked:          {len(blocked)}")
    for entry in report['blocked_by_user']:
        changes = ', '.join(f"CL {c}" if c.isdigit() else 'default CL' for c in entry['changes'])
        print(f"      @{entry['user']}: {entry['count']} blockers ({changes})")
    print(f"  broken target:    {len(broken)}")
    print(f"  non-writable:     {len(non_writable)}")
    print()
    print(f"Wrote {args.out_safe}")
    print(f"Wrote {args.out_report}")


if __name__ == '__main__':
    main()
