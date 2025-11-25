from __future__ import annotations
from src.local_agent.tools.generated.echo_test import EchoTestTool

def test_generated_echo_test():
    t = EchoTestTool()
    r = t.run(text="hello")
    assert r.ok and r.content == "hello"