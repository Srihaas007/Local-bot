
from __future__ import annotations
from typing import Any, Dict
from ..base import Tool, ToolResult

class WordCountTool(Tool):
    name = "word_count"
    description = "Count words in a given text"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }

    def run(self, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text", "")
        n = len([w for w in text.split() if w])
        return ToolResult(ok=True, content=str(n))
