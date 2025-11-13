from __future__ import annotations
from typing import Any, Dict
import os
from ..base import Tool, ToolResult


class TextToSpeechTool(Tool):
    name = "text_to_speech"
    description = "Convert text to speech and save to an audio file using pyttsx3 (offline)."

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "out_path": {"type": "string", "description": "Output audio file path (.wav recommended)"}
                },
                "required": ["text", "out_path"],
            },
        }

    def run(self, **kwargs: Any) -> ToolResult:
        try:
            import pyttsx3  # type: ignore
        except Exception:
            return ToolResult(ok=False, content="Missing dependency: pip install pyttsx3")
        text = kwargs.get("text", "")
        out_path = kwargs.get("out_path")
        if not out_path:
            return ToolResult(ok=False, content="out_path is required")
        try:
            engine = pyttsx3.init()
            # Use save_to_file to write to a file (supported by SAPI on Windows)
            engine.save_to_file(text, out_path)
            engine.runAndWait()
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return ToolResult(ok=True, content=f"Wrote {out_path}")
            return ToolResult(ok=False, content="TTS completed but output file not found or empty")
        except Exception as e:
            return ToolResult(ok=False, content=f"TTS error: {e}")
