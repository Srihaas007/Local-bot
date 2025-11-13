from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str


@dataclass
class ModelResponse:
    text: str


class ModelProvider:
    """Abstract provider interface."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def chat(self, messages: List[Message], tools_schema: Optional[List[Dict[str, Any]]] = None, **gen_kwargs: Any) -> ModelResponse:
        """Return a single assistant message as text.
        Providers should implement this.
        """
        raise NotImplementedError
