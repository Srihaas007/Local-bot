from __future__ import annotations
from typing import Any, Dict
from ..base import Tool, ToolResult

class EchoTestTool(Tool):
    name = "echo_test"
    description = "Echoes input text"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']}
        }

    def run(self, **kwargs: Any) -> ToolResult:
        # Echo the 'text' field or summarize inputs
        if "text" in kwargs:
            return ToolResult(ok=True, content=str(kwargs.get("text", "")))
        return ToolResult(ok=True, content=str(kwargs))