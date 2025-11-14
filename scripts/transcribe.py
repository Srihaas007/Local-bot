#!/usr/bin/env python
"""Simple command-line transcription using the existing SpeechToTextTool.

Usage (PowerShell):
  .\.venv\Scripts\python.exe scripts\transcribe.py --audio path\to\audio.wav --model .\models\vosk-model-small-en-us-0.15

If --model is omitted, VOSK_MODEL_PATH environment variable must be set.
Audio requirements: 16 kHz, mono, 16-bit PCM WAV.
You can convert with ffmpeg:
  ffmpeg -i input.wav -ar 16000 -ac 1 output.wav
"""
import argparse
import os
import sys

from src.local_agent.tools.generated.speech_to_text import SpeechToTextTool


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline speech-to-text using Vosk via SpeechToTextTool")
    p.add_argument("--audio", required=True, help="Path to WAV file (16kHz mono 16-bit)")
    p.add_argument("--model", required=False, help="Path to Vosk model directory (optional; else uses VOSK_MODEL_PATH env)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    audio = args.audio
    model = args.model or os.getenv("VOSK_MODEL_PATH")

    tool = SpeechToTextTool()
    result = tool.run(audio_path=audio, model_path=model)
    if result.ok:
        print(result.content)
        return 0
    else:
        print(f"ERROR: {result.content}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
