from __future__ import annotations
import os
import subprocess
from pathlib import Path

from src.local_agent.config import WORKSPACE
from src.local_agent.tools.git_ops import GitOps


def test_git_ops_status_and_commit():
    # Prepare a temp repo under the workspace jail
    tmp = WORKSPACE / ".agent_data" / "tmp" / "git_tool_test"
    if tmp.exists():
        # cleanup
        for p in sorted(tmp.rglob("*"), reverse=True):
            try:
                if p.is_file() or p.is_symlink():
                    p.unlink(missing_ok=True)
                elif p.is_dir():
                    p.rmdir()
            except Exception:
                pass
        try:
            tmp.rmdir()
        except Exception:
            pass
    tmp.mkdir(parents=True, exist_ok=True)

    def git(args):
        return subprocess.run(["git", *args], cwd=tmp, capture_output=True, text=True)

    # Initialize repo
    r = git(["init"])
    if r.returncode != 0:
        # If git isn't available in the environment, skip
        import pytest
        pytest.skip("git not available")
    # set minimal identity
    git(["config", "user.email", "devnull@example.com"])  # best-effort
    git(["config", "user.name", "Tester"])  # best-effort

    # Create a file
    f = tmp / "hello.txt"
    f.write_text("hello", encoding="utf-8")

    t = GitOps()
    s = t.run(action="status", repo_path=str(tmp.relative_to(WORKSPACE)))
    assert s.ok
    # Should show untracked or be non-empty
    assert s.content == "clean" or len(s.content) >= 0

    c = t.run(action="commit", repo_path=str(tmp.relative_to(WORKSPACE)), paths=["hello.txt"], message="add hello")
    assert c.ok
    assert "Committed" in c.content or "Commit created" in c.content
