"""Bootstrap config — thin wrapper that re-exports from bootstrap_lib.config.

This file exists for backward compatibility with callers that import
from `engine.config` directly (e.g. via sys.path manipulation).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bootstrap_lib.config import *  # noqa: F401,F403
