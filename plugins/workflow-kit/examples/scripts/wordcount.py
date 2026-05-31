#!/usr/bin/env python
"""Tiny deterministic example script for the workflow-kit `script` strategy.

Reads a text file and prints JSON stats to stdout. A `script` node redirects
stdout to $OUT, so the stats land in the node's output file -- the LLM executor
never sees them. Stdlib-only; runs under any Python.

    python wordcount.py <file>   ->   {"lines": N, "words": N, "chars": N}
"""
import json
import sys


def stats(text):
    return {
        "lines": len(text.splitlines()),
        "words": len(text.split()),
        "chars": len(text),
    }


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print("usage: wordcount.py <file>", file=sys.stderr)
        return 2
    try:
        text = open(argv[0], encoding="utf-8").read()
    except OSError as e:
        print("cannot read " + argv[0] + ": " + str(e), file=sys.stderr)
        return 1
    print(json.dumps(stats(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
