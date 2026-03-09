#!/usr/bin/env python3
"""Bootstrap engine — thin wrapper that delegates to bootstrap_lib.engine.

This file exists for backward compatibility with callers that invoke
the engine directly via `python3 engine/bootstrap_engine.py`.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bootstrap_lib.engine import main

if __name__ == "__main__":
    main()
