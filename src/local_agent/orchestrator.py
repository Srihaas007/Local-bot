from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .agent import Agent, AgentResult
from .model_providers.base import Message

@dataclass
class StepResult:
    step: int
    action: str
    output: str

class Orchestrator:
    def __init__(self, agent: Agent, max_steps: int = 10):
        self.agent = agent
        self.max_steps = max_steps

    def run_task(self, task_description: str) -> List[StepResult]:
        """
        Run a multi-step task until completion or max steps.
        """
        history: List[StepResult] = []
        
        # Initial prompt to start the loop
        current_input = f"Task: {task_description}\n\nPlease make a plan and execute it step by step."
        
        for i in range(self.max_steps):
            # Agent step
            result: AgentResult = self.agent.step(current_input)
            
            step_res = StepResult(
                step=i + 1,
                action=result.used_tool or "reply",
                output=result.output
            )
            history.append(step_res)
            
            # Check for completion (heuristic: agent says "TASK_COMPLETE" or similar, or just stops calling tools)
            # For now, we just stop if it's a reply that looks final, or if user intervenes (not modeled here).
            # A simple heuristic: if it's a reply and contains "Done" or "Complete", we might stop.
            # But for now let's just return the history and let the caller decide, 
            # OR we loop if a tool was used, and stop if it was a reply.
            
            if result.used_tool:
                # Tool was used, output is the result. Feed it back.
                current_input = f"Tool Output: {result.output}"
            else:
                # It was a reply. Assume it's the final answer or a question.
                # In a real loop we might ask "Is this correct?"
                break
                
        return history
