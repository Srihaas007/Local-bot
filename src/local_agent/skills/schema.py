from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class SkillManifest:
    name: str
    description: str
    permissions: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)  # JSON Schema fragment
    outputs: Dict[str, Any] = field(default_factory=dict)  # JSON Schema fragment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions,
            "inputs": self.inputs,
            "outputs": self.outputs,
        }
