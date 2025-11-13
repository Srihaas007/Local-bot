from __future__ import annotations
import importlib
from src.local_agent.skills.manager import SkillManager
from src.local_agent.skills.schema import SkillManifest
from src.local_agent.tools.base import Tool


WORD_COUNT_CODE = '''
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
'''

WORD_COUNT_TEST = '''
from __future__ import annotations
from src.local_agent.tools.generated.word_count import WordCountTool

def test_word_count_tool():
    t = WordCountTool()
    r = t.run(text="hello world")
    assert r.ok and r.content == "2"
'''

def test_install_word_count_skill(tmp_path):
    m = SkillManager()
    manifest = SkillManifest(
        name="word_count",
        description="Count words in text",
        permissions=[],
        inputs={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        outputs={"type": "string"}
    )
    tool_path = m.install_skill(manifest, WORD_COUNT_CODE, WORD_COUNT_TEST, approve=False)
    # Ensure module can be imported
    mod = importlib.import_module("src.local_agent.tools.generated.word_count")
    ToolClass = getattr(mod, "WordCountTool")
    t = ToolClass()
    assert isinstance(t, Tool)
    r = t.run(text="a b c")
    assert r.ok and r.content == "3"
