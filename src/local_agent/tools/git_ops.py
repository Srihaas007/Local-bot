from __future__ import annotations
import subprocess
from typing import Any, Dict, List
from pathlib import Path

from .base import Tool, ToolResult
from .file_tools import _jail


class GitOps(Tool):
    name = "git_ops"
    description = "Lightweight git operations (status/diff/commit) within a workspace-relative repo path"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "diff", "commit"],
                        "description": "Which git action to run",
                    },
                    "repo_path": {"type": "string", "default": "."},
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Paths for diff/commit",
                    },
                    "message": {"type": "string", "description": "Commit message"},
                },
                "required": ["action"],
            },
        }

    def _run_git(self, repo: Path, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)

    def run(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        repo = _jail(kwargs.get("repo_path", "."))
        paths: List[str] = list(kwargs.get("paths", []) or [])
        message: str = kwargs.get("message", "")

        try:
            # sanity: ensure it's a git repo
            p = self._run_git(repo, ["rev-parse", "--is-inside-work-tree"])
            if p.returncode != 0 or "true" not in (p.stdout or "").strip():
                return ToolResult(ok=False, content=f"Not a git repository: {repo}")
        except FileNotFoundError:
            return ToolResult(ok=False, content="git not found on PATH")

        if action == "status":
            r = self._run_git(repo, ["status", "--porcelain"])
            if r.returncode == 0:
                out = r.stdout.strip()
                return ToolResult(ok=True, content=out or "clean")
            return ToolResult(ok=False, content=r.stderr.strip())

        if action == "diff":
            args = ["diff"]
            if paths:
                args += ["--", *paths]
            r = self._run_git(repo, args)
            if r.returncode == 0:
                return ToolResult(ok=True, content=r.stdout.strip() or "(no diff)")
            return ToolResult(ok=False, content=r.stderr.strip())

        if action == "commit":
            if not message:
                return ToolResult(ok=False, content="Commit message is required")
            add_args = ["add"] + (paths if paths else ["-A"])
            a = self._run_git(repo, add_args)
            if a.returncode != 0:
                return ToolResult(ok=False, content=a.stderr.strip() or "git add failed")
            c = self._run_git(repo, ["commit", "-m", message])
            if c.returncode != 0:
                return ToolResult(ok=False, content=c.stderr.strip() or "git commit failed")
            h = self._run_git(repo, ["rev-parse", "--short", "HEAD"])
            if h.returncode == 0:
                return ToolResult(ok=True, content=f"Committed {h.stdout.strip()}")
            return ToolResult(ok=True, content="Commit created")

        return ToolResult(ok=False, content=f"Unknown action: {action}")
