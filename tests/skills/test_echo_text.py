from __future__ import annotations
from src.local_agent.tools.generated.echo_text import EchoTextTool

def test_generated_echo_text():
    t = EchoTextTool()
    r = t.run(text="hello")
    assert r.ok and r.content == "hello"
