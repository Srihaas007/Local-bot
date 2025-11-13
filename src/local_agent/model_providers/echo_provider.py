from __future__ import annotations
from typing import List, Optional, Dict, Any
from .base import ModelProvider, ModelResponse, Message


class EchoProvider(ModelProvider):
    """A trivial provider used for tests and wiring.
    It just echoes the last user message.
    """

    def chat(self, messages: List[Message], tools_schema: Optional[List[Dict[str, Any]]] = None, **gen_kwargs: Any) -> ModelResponse:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return ModelResponse(text=f"Echo: {last_user}")

    def stream_chat(self, messages: List[Message], tools_schema: Optional[List[Dict[str, Any]]] = None, **gen_kwargs: Any):
        # Just a single chunk for echo
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        yield f"Echo: {last_user}"
