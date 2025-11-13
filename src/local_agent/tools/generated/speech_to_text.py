from __future__ import annotations
from typing import Any, Dict
import os
import wave
from ..base import Tool, ToolResult


class SpeechToTextTool(Tool):
    name = "speech_to_text"
    description = "Transcribe a WAV audio file to text using Vosk (offline)."

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "audio_path": {"type": "string", "description": "Path to a 16kHz mono WAV file"},
                    "model_path": {"type": "string", "description": "Path to Vosk model directory (optional; else env VOSK_MODEL_PATH)"},
                },
                "required": ["audio_path"],
            },
        }

    def run(self, **kwargs: Any) -> ToolResult:
        try:
            import vosk  # type: ignore
        except Exception:
            return ToolResult(ok=False, content="Missing dependency: pip install vosk and download a Vosk model (set VOSK_MODEL_PATH)")

        audio_path = kwargs.get("audio_path")
        model_path = kwargs.get("model_path") or os.getenv("VOSK_MODEL_PATH")
        if not audio_path or not os.path.exists(audio_path):
            return ToolResult(ok=False, content=f"Audio file not found: {audio_path}")
        if not model_path or not os.path.isdir(model_path):
            return ToolResult(ok=False, content="Vosk model not found. Provide --model_path or set VOSK_MODEL_PATH to a valid model dir.")
        try:
            wf = wave.open(audio_path, "rb")
        except Exception as e:
            return ToolResult(ok=False, content=f"Failed to open WAV: {e}")
        try:
            if wf.getnchannels() != 1:
                return ToolResult(ok=False, content="WAV must be mono")
            if wf.getsampwidth() != 2:
                return ToolResult(ok=False, content="WAV must be 16-bit PCM")
            rate = wf.getframerate()
            if rate not in (16000, 8000, 22050, 44100):
                # Vosk resampler not included; recommend 16000
                # It may still work for some rates
                pass
            model = vosk.Model(model_path)
            rec = vosk.KaldiRecognizer(model, rate)
            transcript_parts = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    import json as _json
                    res = _json.loads(rec.Result())
                    if "text" in res:
                        transcript_parts.append(res["text"])  # type: ignore
            import json as _json
            final = _json.loads(rec.FinalResult())
            if "text" in final:
                transcript_parts.append(final["text"])  # type: ignore
            text = " ".join([t for t in transcript_parts if t])
            return ToolResult(ok=True, content=text.strip())
        except Exception as e:
            return ToolResult(ok=False, content=f"Transcription error: {e}")
        finally:
            try:
                wf.close()
            except Exception:
                pass
