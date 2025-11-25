import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from local_agent.orchestrator import Orchestrator
from local_agent.agent import Agent
from local_agent.model_providers.base import ModelProvider, Message, ModelResponse

# Mock provider for testing
class MockProvider(ModelProvider):
    def __init__(self):
        self.calls = 0
        
    def chat(self, history: list[Message], tools_schema: list[dict] = None, **kwargs) -> ModelResponse:
        self.calls += 1
        last_msg = history[-1].content
        
        if "Task:" in last_msg:
            # First step: propose a tool call
            return ModelResponse(text='{"type": "tool", "name": "echo_tool", "args": {"text": "step1"}}')
        elif "Tool Output" in last_msg:
            # Second step: finish
            return ModelResponse(text='{"type": "reply", "content": "Task complete."}')
        else:
            return ModelResponse(text='{"type": "reply", "content": "Unknown state"}')

    def stream_chat(self, *args, **kwargs):
        yield self.chat(*args, **kwargs).text

# Mock tool
from local_agent.tools.base import Tool, ToolResult
class EchoTool(Tool):
    name = "echo_tool"
    description = "Echo"
    def schema(self): return {"name": "echo_tool"}
    def run(self, text=""): return ToolResult(ok=True, content=f"Echo: {text}")

def test_orchestrator():
    print("Testing Orchestrator...")
    
    # Setup
    provider = MockProvider()
    agent = Agent(provider)
    # Inject mock tool
    from local_agent.agent import TOOL_MAP
    TOOL_MAP["echo_tool"] = EchoTool()
    
    orch = Orchestrator(agent, max_steps=5)
    
    # Run
    steps = orch.run_task("Do a two-step task")
    
    # Verify
    if len(steps) != 2:
        print(f"ERROR: Expected 2 steps, got {len(steps)}")
        for s in steps: print(s)
        sys.exit(1)
        
    if steps[0].action != "echo_tool":
        print(f"ERROR: Step 1 action mismatch: {steps[0].action}")
        sys.exit(1)
        
    if "Task complete" not in steps[1].output:
        print(f"ERROR: Step 2 output mismatch: {steps[1].output}")
        sys.exit(1)
        
    print("Orchestrator verification passed.")

if __name__ == "__main__":
    test_orchestrator()
