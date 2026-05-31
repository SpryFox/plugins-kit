import sys
from pathlib import Path

# Make workflow_kit_lib importable when these tests run under the repo-root pytest.
PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins" / "workflow-kit"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = PLUGIN_ROOT / "examples"
