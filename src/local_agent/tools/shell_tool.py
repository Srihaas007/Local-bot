from __future__ import annotations
import subprocess
from typing import Any, Dict
from ..config import FLAGS
from .base import Tool, ToolResult


class ShellRun(Tool):
    name = "shell_run"
    description = "Run a command in the system shell (disabled unless allowed)"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "Command line"},
                    "timeout": {"type": "integer", "default": 30},
                },
                "required": ["cmd"],
            },
        }

    def run(self, **kwargs: Any) -> ToolResult:
        if not FLAGS.allow_shell:
            return ToolResult(ok=False, content="Shell tool disabled. Set LOCAL_AGENT_ALLOW_SHELL=1 to enable.")
        cmd = kwargs.get("cmd")
        timeout = int(kwargs.get("timeout", 30))
        try:
            out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            if out.returncode == 0:
                return ToolResult(ok=True, content=out.stdout.strip())
            else:
                return ToolResult(ok=False, content=out.stderr.strip() or f"Non-zero exit ({out.returncode})")
        except Exception as e:
            return ToolResult(ok=False, content=f"Shell error: {e}")
