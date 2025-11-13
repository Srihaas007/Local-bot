# Local Agent (No Ollama Required)

A small, extensible local agent you can run entirely on your Windows machine. It supports:

- Model providers:
  - LlamaCppProvider (GGUF via `llama-cpp-python`) — optional
  - TransformersProvider (Hugging Face) — optional
  - EchoProvider (for tests; no heavy deps)
- Tools: read/write/list files, run shell (scoped), and a simple memory store (SQLite)
- Agent loop: JSON tool-calling protocol with human approval gates
- No external services required by default.

Your hardware: i9-13th gen, 16GB RAM, RTX 4070 8GB — you can comfortably run 7B–8B models locally with good speed. 13B may work with 4-bit quantization on GPU but expect tighter VRAM.

## Recommended models (practical picks)

- General assistant (fast, solid):
  - Llama 3.1 8B Instruct (HF Transformers with 4-bit) or GGUF quant via llama.cpp
  - Alternative: Qwen2.5 7B Instruct (HF or GGUF)
- Coding tasks:
  - Qwen2.5-Coder 7B Instruct (HF or GGUF)
  - Alternative: DeepSeek-Coder 6.7B Instruct (HF)
- Embeddings (optional, CPU OK):
  - all-MiniLM-L6-v2 or bge-small-en-v1.5 (via sentence-transformers) — only needed if you add semantic memory

## Project layout

- `src/local_agent/agent.py` — agent loop with JSON tool-calls
- `src/local_agent/model_providers/` — pluggable model providers
- `src/local_agent/tools/` — file and shell tools with path jail
- `src/local_agent/memory/sqlite_memory.py` — simple long-term memory
- `src/local_agent/cli.py` — CLI entry to chat with the agent
- `tests/` — lightweight tests using a dummy provider

## Install (minimal, no heavy ML libs)

Create a virtual environment and install core deps:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run tests (uses Echo/Dummy providers only):

```powershell
pytest -q
```

## Optional: Enable a real local model

### Option A: llama-cpp-python (GGUF)

- Install a wheel (CPU easiest):

```powershell
pip install llama-cpp-python
```

- Place a GGUF model locally, e.g. `models\llama3.1-8b-instruct.Q4_K_M.gguf`.
- Run CLI with provider `llamacpp` and point to the GGUF path.

### Option B: Transformers + (CUDA) Torch

- Install PyTorch with CUDA for Windows (see pytorch.org for the correct command), then:

```powershell
pip install transformers bitsandbytes
```

- Use a model like `meta-llama/Meta-Llama-3.1-8B-Instruct` or `Qwen/Qwen2.5-7B-Instruct` with 4-bit.

Note: Large ML installs can take time; the agent still works with EchoProvider meanwhile.

## Optional: Semantic memory (embeddings)

Semantic memory is optional and off by default. To enable it:

1) Install sentence-transformers (will pull PyTorch CPU by default):

```powershell
pip install sentence-transformers
```

2) The agent will automatically compute embeddings for new memories and use semantic search. If not installed, it will fall back to keyword search.

## Usage

```powershell
python -m src.local_agent.cli --provider echo
```

Type messages. The agent will respond or request a tool call in JSON. With a real provider, it will reason and call tools as needed.

Examples of agent tool outputs are printed with diffs and prompts for approval.

### Skills CLI

Manage skills (self-extended tools) via a separate CLI:

```powershell
python -m src.local_agent.skills_cli list

# Install from files (requires a manifest.json and a tool .py; tests optional)
python -m src.local_agent.skills_cli install --manifest skills\word_count\manifest.json --code src\local_agent\tools\generated\word_count.py --auto-approve

# Run only skills tests
python -m src.local_agent.skills_cli run-tests --path tests\skills

# Propose a new skill (echo)
python -m src.local_agent.skills_cli propose --name echo_text --description "Echo the input" --auto-approve
```

## Safety & sandboxing

- Path jail: tools are restricted to the workspace folder by default.
- Shell tool: disabled by default; enable with `--allow-shell`.
- Approval gate: tool executions pause for your confirmation.

## Next steps

- Add semantic memory (sentence-transformers + SQLite vector table)
- Add LangGraph workflow (approval gates, retries) if you need more complex flows
- Add a simple web UI

## Skill factory (self-extend) — MVP

The project includes a minimal skill manager that can install new tools with a manifest, code, and optional tests. Installed tools live under `src/local_agent/tools/generated/` and are auto-loaded by the agent.

Example: install a simple word_count tool (from tests):

1) Look at `tests/test_skill_factory.py` for an example manifest and tool code.
2) Use the `SkillManager` in a short Python snippet to install it, or copy the example into your own script.
3) After installation, the tool `word_count` will be available to the agent as a regular tool.

Notes:
- Tests for a skill can be run selectively; in this MVP they run in the same environment (no per-skill venv yet).
- Approval gates are supported by your workflow: generate → test → review → install.

### Optional speech skills (offline)

Two example skills are included and auto-loaded:
- speech_to_text (Vosk): transcribes a 16kHz mono WAV to text.
- text_to_speech (pyttsx3): converts text to speech and saves to a file.

Dependencies (optional):

```powershell
pip install pyttsx3
pip install vosk
# Download a Vosk model (e.g., small English) and set VOSK_MODEL_PATH to its directory
# https://alphacephei.com/vosk/models
```

Usage examples:

- TTS to a file:

```powershell
python - <<'PY'
from src.local_agent.tools.generated.text_to_speech import TextToSpeechTool
print(TextToSpeechTool().run(text="Hello from Local-bot", out_path="tts_demo.wav"))
PY
```

- STT from a WAV:

```powershell
python - <<'PY'
import os
os.environ['VOSK_MODEL_PATH'] = r'.\\models\\vosk-model-small-en-us-0.15'  # adjust path
from src.local_agent.tools.generated.speech_to_text import SpeechToTextTool
print(SpeechToTextTool().run(audio_path="demo.wav"))
PY
```
