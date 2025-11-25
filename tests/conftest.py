"""Test configuration.

Ensures the repository root is on sys.path so imports like
`from src.local_agent...` work in CI (GitHub Actions) and local runs.

The project uses a src/ layout but is not installed as a package during
test collection, so we manually prepend the repo root to sys.path.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
