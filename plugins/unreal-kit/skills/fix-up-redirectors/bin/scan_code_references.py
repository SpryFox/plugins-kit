"""Scan project source for hardcoded UE content paths and cache them.

Host-side. Writes a YAML keyed by `generated_at` so consumers can decide
whether to re-scan. Default cache location is `./.local-data/code_references.yaml`
relative to cwd.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
from code_refs import DEFAULT_EXTENSIONS, scan, save


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.getcwd(), help='Project root to scan (default: cwd)')
    ap.add_argument('--out', default=os.path.join('.local-data', 'code_references.yaml'),
                    help='Output YAML path (default: ./.local-data/code_references.yaml)')
    ap.add_argument('--extensions', default=','.join(DEFAULT_EXTENSIONS),
                    help='Comma-separated file extensions to scan')
    args = ap.parse_args()

    extensions = tuple(e.strip() if e.strip().startswith('.') else '.' + e.strip()
                       for e in args.extensions.split(',') if e.strip())

    print(f"Scanning {args.root} for code references...")
    t0 = time.time()
    refs, file_count, scanned_count = scan(args.root, extensions=extensions)
    elapsed = time.time() - t0

    save(args.out, refs, args.root, file_count, scanned_count, extensions)

    print(f"Scanned {file_count} files ({scanned_count} matched extension) in {elapsed:.1f}s")
    print(f"Found {len(refs)} unique content references")
    print(f"Wrote {args.out}")


if __name__ == '__main__':
    main()
