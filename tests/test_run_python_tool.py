from __future__ import annotations
import os
from src.local_agent.tools.run_python import RunPython


def test_run_python_basic_output():
    t = RunPython()
    r = t.run(code="print(1+2)")
    assert r.ok and r.content.strip() == "3"


def test_run_python_timeout():
    t = RunPython()
    r = t.run(code="import time; time.sleep(2)", timeout=1)
    assert not r.ok
    assert "Timeout" in r.content


def test_run_python_restricted_fs():
    t = RunPython()
    # Try to read outside sandbox using an absolute path if available or parent traversal
    # Parent traversal should be blocked by our open wrapper
    code = (
        "from pathlib import Path\n"
        "# attempt to escape sandbox\n"
        "try:\n"
        "    print(open('../README.md').read()[:10])\n"
        "except Exception as e:\n"
        "    print(type(e).__name__)\n"
    )
    r = t.run(code=code, keep=False, restricted=True)
    assert r.ok
    # Expect PermissionError to be printed by code
    assert "PermissionError" in r.content
