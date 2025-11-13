from __future__ import annotations
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .model_providers.base import ModelProvider, Message
from .tools import Tool, ReadFile, WriteFile, ListFiles, ShellRun, WebFetch
from .memory import MemoryStore, MemoryItem
from .config import FLAGS

SYSTEM_PROMPT = (
    "You are a local coding and automation assistant. "
    "When a tool is needed, respond ONLY with a single-line JSON object: "
    "{\"type\":\"tool\", \"name\":<tool_name>, \"args\":{...}}. "
    "Otherwise respond with {\"type\":\"reply\", \"content\":<message>}.")


def _load_tools() -> List[Tool]:
    # Base tools
    tools: List[Tool] = [ReadFile(), WriteFile(), ListFiles(), ShellRun(), WebFetch()]
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
        self.history: List[Message] = [Message(role="system", content=SYSTEM_PROMPT)]
        self._pending_action: Optional[Dict[str, Any]] = None

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
            self._append("tool", f"{name}: {result.content}")
            if result.ok and name == "write_file":
                self.memory.add([MemoryItem(kind="file_write", text=str(args))])
            return AgentResult(output=("OK: " if result.ok else "ERR: ") + result.content, used_tool=name)

        # Normal turn: retrieve relevant memory, then ask the model what to do
        mem_hits = self.memory.search(user_text, limit=3)
        if mem_hits:
            mem_text = "\n".join(f"- [{k}] {t}" for (_id, k, t) in mem_hits)
            self._append("system", f"Relevant memory:\n{mem_text}")
        self._append("user", user_text)
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
            self._append("tool", f"{name}: {result.content}")
            if result.ok and name == "write_file":
                self.memory.add([MemoryItem(kind="file_write", text=str(args))])
            return AgentResult(output=("OK: " if result.ok else "ERR: ") + result.content, used_tool=name)
        else:
            # Normal reply; store memory of important items (very naive heuristic)
            if len(user_text) < 400:
                self.memory.add([MemoryItem(kind="note", text=user_text)])
            return AgentResult(output=resp.text)

    def step_stream(self, user_text: str, temperature: float = 0.2, max_tokens: int = 512):
        """Stream tokens to the caller while accumulating the full response, then finalize like step().
        Yields chunks of text when appropriate (i.e., non-JSON tool call). Returns an AgentResult at the end.
        """
        # Prepare memory context
        mem_hits = self.memory.search(user_text, limit=3)
        if mem_hits:
            mem_text = "\n".join(f"- [{k}] {t}" for (_id, k, t) in mem_hits)
            self._append("system", f"Relevant memory:\n{mem_text}")
        self._append("user", user_text)

        # Stream from provider
        chunks: List[str] = []
        saw_non_ws = False
        json_mode = False
        for part in self.provider.stream_chat(self.history, tools_schema=TOOL_SCHEMA, temperature=temperature, max_tokens=max_tokens):
            if not part:
                continue
            if not saw_non_ws:
                # Determine if this looks like JSON; if so, don't stream live
                for ch in part:
                    if not ch.isspace():
                        saw_non_ws = True
                        if ch == '{':
                            json_mode = True
                        break
            chunks.append(part)
            if not json_mode:
                # Yield live chunks to caller
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
                # Store pending and signal approval prompt (do not stream tool JSON)
                self._pending_action = action
                yield "\n"
                yield f"Tool requested: {name} {args}. Approve? (y/n)"
                return AgentResult(output=f"Tool requested: {name} {args}. Approve? (y/n)", used_tool=name)
            # Execute immediately if no approval required
            result = tool.run(**args)
            self._append("tool", f"{name}: {result.content}")
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
        # Try to find a JSON object in the response
        s = text.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                obj = json.loads(s)
                if isinstance(obj, dict) and obj.get("type") in {"tool", "reply"}:
                    return obj
            except Exception:
                return None
        return None
