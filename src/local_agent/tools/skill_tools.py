from __future__ import annotations
import json
from typing import Any, Dict, List
from .base import Tool, ToolResult
from ..skills.manager import SkillManager
from ..skills.schema import SkillManifest
from ..skills.generator import generate_skill

class ProposeSkill(Tool):
    name = "propose_skill"
    description = "Propose a new skill by generating a manifest and code. Returns the proposal for review."

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the skill (snake_case)"},
                    "description": {"type": "string", "description": "Description of what the skill does"},
                    "inputs": {"type": "object", "description": "JSON schema for inputs"},
                    "pattern": {"type": "string", "enum": ["echo"], "default": "echo"}
                },
                "required": ["name", "description"]
            }
        }

    def run(self, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name", "")
        desc = kwargs.get("description", "")
        inputs = kwargs.get("inputs", {})
        pattern = kwargs.get("pattern", "echo")

        if not name or not desc:
            return ToolResult(ok=False, content="Name and description are required.")

        manifest = SkillManifest(
            name=name,
            description=desc,
            inputs=inputs
        )
        
        try:
            tool_code, test_code = generate_skill(manifest, pattern=pattern)
            return ToolResult(ok=True, content=f"Proposed skill '{name}'.\n\nManifest:\n{json.dumps(manifest.to_dict(), indent=2)}\n\nCode:\n{tool_code}\n\nTests:\n{test_code}")
        except Exception as e:
            return ToolResult(ok=False, content=f"Error generating skill: {e}")


class InstallSkill(Tool):
    name = "install_skill"
    description = "Install a previously proposed skill. Requires manifest, code, and optional tests."

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "manifest": {"type": "object", "description": "The full manifest JSON"},
                    "code": {"type": "string", "description": "The python code for the tool"},
                    "tests": {"type": "string", "description": "The python code for tests"},
                    "approve": {"type": "boolean", "default": True}
                },
                "required": ["manifest", "code"]
            }
        }

    def run(self, **kwargs: Any) -> ToolResult:
        manifest_dict = kwargs.get("manifest", {})
        code = kwargs.get("code", "")
        tests = kwargs.get("tests", "")
        approve = kwargs.get("approve", True)

        if not manifest_dict or not code:
            return ToolResult(ok=False, content="Manifest and code are required.")

        try:
            manifest = SkillManifest(**manifest_dict)
            manager = SkillManager()
            path = manager.install_skill(manifest, code, tests if tests else None, approve=approve)
            return ToolResult(ok=True, content=f"Skill '{manifest.name}' installed at {path}")
        except Exception as e:
            return ToolResult(ok=False, content=f"Error installing skill: {e}")
