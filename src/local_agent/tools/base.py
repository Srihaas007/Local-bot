from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ToolResult:
    ok: bool
    content: str


class Tool:
    name: str
    description: str

    def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }
