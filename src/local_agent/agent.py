from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .model_providers.base import ModelProvider, Message
from .tools import Tool, ReadFile, WriteFile, ListFiles, ShellRun, WebFetch
from .tools.skill_tools import ProposeSkill, InstallSkill
from .memory import MemoryStore, MemoryItem
from .config import FLAGS

SYSTEM_PROMPT = (
    "You are a local coding and automation assistant. "
    "You have access to the following tools:\n"
    "{tool_descriptions}\n\n"
    "To use a tool, you MUST use the following format:\n"
    "Thought: <your reasoning here>\n"
    "Action: \n"
    "```json\n"
    "{{\"type\": \"tool\", \"name\": \"<tool_name>\", \"args\": {{<args>}}}}\n"
    "```\n\n"
    "If you do not need a tool, just respond with your answer.\n"
    "Always think step-by-step."
)


def _load_tools() -> List[Tool]:
    # Base tools
    tools: List[Tool] = [ReadFile(), WriteFile(), ListFiles(), ShellRun(), WebFetch(), ProposeSkill(), InstallSkill()]
    # Include any generated tools by scanning subclasses
    try:
        # Discover subclasses defined in imported modules
        for cls in Tool.__subclasses__():
            # Skip base known ones by name
            if cls in {ReadFile, WriteFile, ListFiles, ShellRun, WebFetch}:
                continue
            try:
                inst = cls()  # type: ignore[call-arg]
                tools.append(inst)
            except Exception:
                continue
    except Exception:
        pass
    return tools

tool_instances: List[Tool] = _load_tools()
TOOL_MAP: Dict[str, Tool] = {t.name: t for t in tool_instances}
TOOL_SCHEMA = [t.schema() for t in tool_instances]


@dataclass
class AgentResult:
    output: str
    used_tool: Optional[str] = None


class Agent:
    def __init__(self, provider: ModelProvider, memory: Optional[MemoryStore] = None):
        self.provider = provider
        self.memory = memory or MemoryStore()
        # Dynamic system prompt based on available tools
        tools_desc = "\n".join([f"- {t.name}: {t.description}" for t in tool_instances])
        self.system_prompt = SYSTEM_PROMPT.format(tool_descriptions=tools_desc)
        self.history: List[Message] = [Message(role="system", content=self.system_prompt)]
        self._pending_action: Optional[Dict[str, Any]] = None

    @property
    def tools(self) -> List[Tool]:
        return tool_instances

    def _append(self, role: str, content: str) -> None:
        self.history.append(Message(role=role, content=content))

    def step(self, user_text: str, approve: Optional[bool] = None) -> AgentResult:
        # If we have a pending tool action and user is approving/denying, handle it directly
        if self._pending_action is not None and FLAGS.approve_tools and approve is not None:
            action = self._pending_action
            name = action.get("name", "")
            args = action.get("args", {})
            if approve is False:
                self._pending_action = None
                return AgentResult(output="Tool execution denied by user.")
            tool = TOOL_MAP.get(name)
            if not tool:
                self._pending_action = None
                return AgentResult(output=f"Unknown tool: {name}")
            result = tool.run(**args)
            self._pending_action = None
            self._append("tool", f"{name} output: {result.content}")
            if result.ok and name == "write_file":
                self.memory.add([MemoryItem(kind="file_write", text=str(args))])
            return AgentResult(output=("OK: " if result.ok else "ERR: ") + result.content, used_tool=name)

        # Normal turn: retrieve relevant memory, then ask the model what to do
        mem_hits = self.memory.search(user_text, limit=3)
        if mem_hits:
            mem_text = "\n".join(f"- [{k}] {t}" for (_id, k, t) in mem_hits)
            self._append("system", f"Relevant memory:\n{mem_text}")
        
        self._append("user", user_text)
        
        # Get response
        resp = self.provider.chat(self.history, tools_schema=TOOL_SCHEMA, temperature=0.2)
        self._append("assistant", resp.text)
        
        action = self._parse_action(resp.text)
        if action and action.get("type") == "tool":
            name = action.get("name", "")
            args = action.get("args", {})
            tool = TOOL_MAP.get(name)
            if not tool:
                return AgentResult(output=f"Unknown tool: {name}")
            
            if FLAGS.approve_tools:
                # Store pending and ask for approval
                self._pending_action = action
                return AgentResult(output=f"Tool requested: {name} {args}. Approve? (y/n)", used_tool=name)
            
            # Execute immediately if no approval required
            result = tool.run(**args)
            self._append("tool", f"{name} output: {result.content}")
            if result.ok and name == "write_file":
                self.memory.add([MemoryItem(kind="file_write", text=str(args))])
            
            # Return the tool output so the orchestrator or UI knows what happened
            return AgentResult(output=("OK: " if result.ok else "ERR: ") + result.content, used_tool=name)
        else:
            # Normal reply; store memory of important items (very naive heuristic)
            if len(user_text) < 400:
                self.memory.add([MemoryItem(kind="note", text=user_text)])
            return AgentResult(output=resp.text)

    def step_stream(self, user_text: str, temperature: float = 0.2, max_tokens: int = 512):
        """Stream tokens to the caller while accumulating the full response, then finalize like step().
        Yields chunks of text when appropriate. Returns an AgentResult at the end.
        """
        # Prepare memory context
        mem_hits = self.memory.search(user_text, limit=3)
        if mem_hits:
            mem_text = "\n".join(f"- [{k}] {t}" for (_id, k, t) in mem_hits)
            self._append("system", f"Relevant memory:\n{mem_text}")
        self._append("user", user_text)

        # Stream from provider
        chunks: List[str] = []
        
        # We stream everything. The UI/Client should handle hiding the JSON block if desired, 
        # or we can try to detect it. For now, stream raw.
        for part in self.provider.stream_chat(self.history, tools_schema=TOOL_SCHEMA, temperature=temperature, max_tokens=max_tokens):
            if not part:
                continue
            chunks.append(part)
            yield part

        full_text = "".join(chunks).strip()
        self._append("assistant", full_text)

        # Finalize similar to step()
        action = self._parse_action(full_text)
        if action and action.get("type") == "tool":
            name = action.get("name", "")
            args = action.get("args", {})
            tool = TOOL_MAP.get(name)
            if not tool:
                yield "\n"
                yield f"Unknown tool: {name}"
                return AgentResult(output=f"Unknown tool: {name}")
            
            if FLAGS.approve_tools:
                self._pending_action = action
                yield "\n"
                yield f"Tool requested: {name} {args}. Approve? (y/n)"
                return AgentResult(output=f"Tool requested: {name} {args}. Approve? (y/n)", used_tool=name)
            
            # Execute immediately
            result = tool.run(**args)
            self._append("tool", f"{name} output: {result.content}")
            if result.ok and name == "write_file":
                self.memory.add([MemoryItem(kind="file_write", text=str(args))])
            
            yield "\n"
            yield ("OK: " if result.ok else "ERR: ") + result.content
            return AgentResult(output=("OK: " if result.ok else "ERR: ") + result.content, used_tool=name)
        else:
            if len(user_text) < 400:
                self.memory.add([MemoryItem(kind="note", text=user_text)])
            return AgentResult(output=full_text)

    @staticmethod
    def _parse_action(text: str) -> Optional[Dict[str, Any]]:
        # Robust JSON extraction: look for ```json ... ``` or just { ... }
        
        # 1. Try markdown code block
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # 2. Try finding the first outer brace pair
        # This is a simple heuristic finding the first '{' and the last '}'
        # It might fail on nested structures if not careful, but usually sufficient for tool calls.
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = text[start:end+1]
                obj = json.loads(json_str)
                if isinstance(obj, dict) and obj.get("type") == "tool":
                    return obj
        except:
            pass
            
        return None
