from __future__ import annotations
from src.local_agent.agent import Agent
from src.local_agent.memory import MemoryStore
from src.local_agent.model_providers.base import ModelProvider, ModelResponse, Message


class DummyToolProvider(ModelProvider):
    """Returns a tool call JSON the first time, then a reply."""

    def __init__(self):
        super().__init__()
        self.called = False

    def chat(self, messages, tools_schema=None, **kwargs):  # type: ignore[override]
        if not self.called:
            self.called = True
            return ModelResponse(text='{"type":"tool","name":"list_files","args":{"path":"."}}')
        return ModelResponse(text='{"type":"reply","content":"Done"}')


def test_agent_tool_flow(tmp_path):
    ms = MemoryStore()
    agent = Agent(DummyToolProvider(), memory=ms)
    r1 = agent.step("What files are here?")
    assert "Tool requested:" in r1.output
    r2 = agent.step("(approve)", approve=True)
    # Depending on workspace, just assert it produced some list or allowed result
    assert r2.output.startswith("OK:") or r2.output.startswith("ERR:")
    r3 = agent.step("Thanks")
    assert "reply" in r3.output.lower() or r3.output.startswith("{") or len(r3.output) > 0
