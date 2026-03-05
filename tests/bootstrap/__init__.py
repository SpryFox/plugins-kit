"""Bootstrap test package — adds lib/ and engine/ to sys.path for imports."""

import os
import sys

BOOTSTRAP_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "bootstrap")
)

lib_path = os.path.join(BOOTSTRAP_ROOT, "lib")
engine_path = os.path.join(BOOTSTRAP_ROOT, "engine")

for p in (lib_path, engine_path):
    if p not in sys.path:
        sys.path.insert(0, p)
