from __future__ import annotations
from typing import Tuple
from .schema import SkillManifest


def generate_skill(manifest: SkillManifest, pattern: str = "echo") -> Tuple[str, str]:
    """
    Generate tool code and a pytest for a simple skill based on the manifest.
    Supported patterns: 'echo' (default).
    """
    name = manifest.name
    class_name = "".join(part.capitalize() for part in name.split("_")) + "Tool"

    if pattern == "echo":
        tool_code = f'''from __future__ import annotations
from typing import Any, Dict
from ..base import Tool, ToolResult

class {class_name}(Tool):
    name = "{name}"
    description = "{manifest.description}"

    def schema(self) -> Dict[str, Any]:
        return {{
            "name": self.name,
            "description": self.description,
            "parameters": {manifest.inputs if manifest.inputs else {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}
        }}

    def run(self, **kwargs: Any) -> ToolResult:
        # Echo the 'text' field or summarize inputs
        if "text" in kwargs:
            return ToolResult(ok=True, content=str(kwargs.get("text", "")))
        return ToolResult(ok=True, content=str(kwargs))
'''
        # Create a basic test that calls the tool with a 'text' param if available
        uses_text = False
        if manifest.inputs and isinstance(manifest.inputs, dict):
            props = manifest.inputs.get("properties", {})
            uses_text = "text" in props
        if not uses_text:
            # default to text
            uses_text = True
        test_code = f'''from __future__ import annotations
from src.local_agent.tools.generated.{name} import {class_name}

def test_generated_{name}():
    t = {class_name}()
    r = t.run(text="hello")
    assert r.ok and r.content == "hello"
'''
        return tool_code, test_code

    # Fallback to echo
    return generate_skill(manifest, pattern="echo")
