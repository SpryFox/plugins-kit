"""Discovery and safe-set file I/O.

CCP: any change to the on-disk shape of redirector data lands here, so all
three phases keep their contract aligned. Stdlib + pyyaml only.
"""
import json
import os

import yaml


def save_discovery(path, scope, records):
    """Write the phase-1 YAML."""
    out = {
        'scope': scope,
        'total': len(records),
        'redirectors': records,
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w') as f:
        yaml.dump(out, f, default_flow_style=False, sort_keys=False)


def load_discovery(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def save_safe_set(path, scope, records):
    """Write the safe-set JSON consumed by phase 3."""
    out = {
        'scope': scope,
        'count': len(records),
        'redirectors': records,
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)


def load_safe_set(path):
    with open(path, 'r') as f:
        return json.load(f)


def save_report(path, report):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(report, f, indent=2)


def save_apply_manifest(path, manifest):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)
