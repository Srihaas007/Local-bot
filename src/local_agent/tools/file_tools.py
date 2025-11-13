from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
from ..config import WORKSPACE
from .base import Tool, ToolResult


def _jail(path: str) -> Path:
    p = (WORKSPACE / path).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise PermissionError("Path escapes workspace jail")
    return p


class ReadFile(Tool):
    name = "read_file"
    description = "Read a UTF-8 text file within the workspace"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path"},
                    "start": {"type": "integer", "description": "1-based start line", "default": 1},
                    "end": {"type": "integer", "description": "inclusive end line", "default": 10_000},
                },
                "required": ["path"],
            },
        }

    def run(self, **kwargs: Any) -> ToolResult:
        path = _jail(kwargs.get("path", ""))
        start = int(kwargs.get("start", 1))
        end = int(kwargs.get("end", 10_000))
        try:
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            snippet = "\n".join(lines[start - 1 : end])
            return ToolResult(ok=True, content=snippet)
        except Exception as e:
            return ToolResult(ok=False, content=f"Error reading file: {e}")


class WriteFile(Tool):
    name = "write_file"
    description = "Write UTF-8 text to a file within the workspace (creates dirs)"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        }

    def run(self, **kwargs: Any) -> ToolResult:
        path = _jail(kwargs.get("path", ""))
        content = kwargs.get("content", "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(ok=True, content=f"Wrote {path.relative_to(WORKSPACE)}")
        except Exception as e:
            return ToolResult(ok=False, content=f"Error writing file: {e}")


class ListFiles(Tool):
    name = "list_files"
    description = "List files and dirs under a workspace-relative path"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
            },
        }

    def run(self, **kwargs: Any) -> ToolResult:
        path = _jail(kwargs.get("path", "."))
        try:
            items = []
            for p in sorted(path.iterdir()):
                kind = "dir" if p.is_dir() else "file"
                items.append(f"{kind}\t{p.relative_to(WORKSPACE)}")
            return ToolResult(ok=True, content="\n".join(items))
        except Exception as e:
            return ToolResult(ok=False, content=f"Error listing files: {e}")
