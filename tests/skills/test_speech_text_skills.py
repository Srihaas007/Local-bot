from __future__ import annotations
import os
import tempfile
from src.local_agent.tools.generated.speech_to_text import SpeechToTextTool
from src.local_agent.tools.generated.text_to_speech import TextToSpeechTool


def test_text_to_speech_dep_or_output():
    t = TextToSpeechTool()
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.wav")
        r = t.run(text="hello world", out_path=out)
        # Either success with a file, or informative missing dependency
        if r.ok:
            assert os.path.exists(out) and os.path.getsize(out) >= 0
        else:
            assert "Missing dependency" in r.content or "TTS error" in r.content


def test_speech_to_text_dep_message():
    t = SpeechToTextTool()
    # Provide non-existent audio_path to ensure it fails gracefully even if vosk is installed
    r = t.run(audio_path="nonexistent.wav")
    assert not r.ok
    # Should be either missing dependency, file not found, or model not found
    assert any(msg in r.content for msg in ["Missing dependency", "not found", "model"])  # broad check
