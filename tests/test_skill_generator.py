from __future__ import annotations
from src.local_agent.skills.schema import SkillManifest
from src.local_agent.skills.generator import generate_skill
from src.local_agent.skills.manager import SkillManager


def test_generate_and_install_echo_skill(tmp_path):
    manifest = SkillManifest(
        name="echo_text",
        description="Echo the input text",
        inputs={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        outputs={"type": "string"},
        permissions=[],
    )
    tool_code, test_code = generate_skill(manifest, pattern="echo")
    assert "class EchoTextTool" in tool_code
    assert "def test_generated_echo_text" in test_code

    mgr = SkillManager()
    tool_path = mgr.install_skill(manifest, tool_code, test_code, approve=True)
    assert tool_path.exists()
