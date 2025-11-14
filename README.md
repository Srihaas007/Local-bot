# Local Agent (No Ollama Required)

A small, extensible local agent you can run entirely on your Windows machine. It supports:

- Model providers:
  - LlamaCppProvider (GGUF via `llama-cpp-python`) — optional
  - TransformersProvider (Hugging Face) — optional
  - EchoProvider (for tests; no heavy deps)
- Tools: read/write/list files, run shell (scoped), web fetch with allowlist, run Python in a sandbox, git ops, and a simple memory store (SQLite)
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

### Built-in tools

- read_file / write_file / list_files — workspace path jail enforced
- web_fetch — HTTP(S) fetch with domain allowlist and size/time/content-type guards (set LOCAL_AGENT_ALLOWED_DOMAINS)
- run_python — run a short Python snippet in a temporary sandbox directory under `.agent_data/sandboxes` with timeout and a best-effort restricted I/O mode (blocks some modules and prevents file access outside the sandbox)
- git_ops — lightweight git status/diff/commit limited to a workspace-relative repo path
- shell_run — disabled by default; enable via env `LOCAL_AGENT_ALLOW_SHELL=1` or CLI flag

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

### Quick command-line transcription script

For convenience, a helper script `scripts/transcribe.py` wraps the `SpeechToTextTool`:

```powershell
# Set model directory once (if not passing --model each time)
$env:VOSK_MODEL_PATH = ".\models\vosk-model-small-en-us-0.15"

# Ensure audio is 16 kHz mono 16-bit WAV; convert if needed:
ffmpeg -i input.wav -ar 16000 -ac 1 input_16k_mono.wav

# Run transcription
python scripts/transcribe.py --audio input_16k_mono.wav

# Or explicitly specify model
python scripts/transcribe.py --audio input_16k_mono.wav --model .\models\vosk-model-small-en-us-0.15
```

If you see an error about missing dependency, install Vosk and download a model:

```powershell
pip install vosk
# Download and extract a model folder from https://alphacephei.com/vosk/models
``` 

Notes:
- Long audio: you can pre-split into chunks with `ffmpeg -i long.wav -f segment -segment_time 30 -c copy chunk%03d.wav output_dir` and iterate.
- Background noise: consider simple noise reduction or using a larger model for better accuracy.
- Alternative (larger but higher accuracy): integrate Whisper (`pip install openai-whisper`) and adapt the script (future enhancement).

### Command Center Modal (Unified UI)

The web UI now includes a floating button (◎) that opens a unified "Command Center" modal with tabs:

Tabs:
1. Chat – Same functionality as the main view; supports streaming toggle.
2. Memory – Search the agent's stored memories.
3. STT – Upload WAV or record live microphone audio and transcribe.
4. TTS – Enter text and generate speech playback.
5. Settings – Client-side Vosk model path field (used for reference; server still relies on environment variable).

How to use:
1. Start server: `python -m uvicorn src.local_agent.web.server:app --host 127.0.0.1 --port 8000`
2. Open browser at http://127.0.0.1:8000/static/index.html
3. Click the ◎ button bottom-right to open the modal.
4. Switch tabs as needed; each tab isolates its outputs.

The original sidebar UI remains; the modal offers a consolidated workspace for multi-task workflows.

### Provider Switching & Chat Persistence

New features (iterated):
- Provider selector (Echo, optional llama.cpp, optional Transformers) in the chat bar.
  - For llama.cpp provide a local GGUF path.
  - For Transformers provide a model name (e.g. `meta-llama/Meta-Llama-3.1-8B-Instruct`).
  - Switch without losing memory state.
- Automatic chat persistence: messages are saved to `localStorage` and restored on reload.
- Inline action cards: the assistant can surface STT, TTS, and Memory search mini widgets directly under its response if relevant.

Endpoints added:
- `GET /provider/list` — returns available providers and current active.
- `POST /provider/set` — body: `{ "name": "llamacpp", "model_path": "models/your.gguf" }` or `{ "name": "transformers", "model_name": "org/model" }`.
- `GET /tools` — list tool schemas currently loaded.
- `POST /run_python` — sandboxed Python execution (code, timeout, restricted).
- `GET /fs/read`, `POST /fs/write`, `POST /fs/upload` — basic file operations under workspace jail.
- `POST /memory/save` — save a memory item; `GET /memory/list` — list recent memories.

### Memory Pinning & Session Export

In the chat UI each message has a subtle star (★) pin button on hover. Clicking it:
- Calls `/memory/save` with kind `chat`.
- Marks the message with a gold outline and PINNED badge.
- Pinned state persists visually (memory stored in SQLite).

Export the whole session (chat + memory snapshot) via Settings → Export session. Produces `session_export.json` with structure:
```json
{
  "chat": [{"role": "user", "text": "Hi", "pinned": false}, ...],
  "memories": [{"id": 12, "kind": "chat", "text": "Important note", "ts": "2025-11-14 12:34:56"}]
}
```

### Model Download (Local)

You can fetch a model directly into `models/` from the UI Settings menu.

Options:
- Direct URL (e.g. GGUF file): paste URL + filename and start download.
- HuggingFace repo: provide `hf_model` (repo id like `TheBloke/Llama-2-7B-GGUF`) and `filename` (exact file name in repo).

Endpoints:
- `POST /model/download` body examples:
  - `{ "url": "https://example.com/model.gguf", "filename": "my.gguf" }`
  - `{ "hf_model": "org/model", "filename": "model.gguf" }`
- `GET /model/status/{job_id}` returns progress fields: `status`, `downloaded`, `total`, `file`.

Progress Notes:
- Direct URL streams in chunks; percentage shown if `Content-Length` provided.
- HuggingFace download uses cache then copies into `models/`.
- Requires `huggingface_hub` for HF downloads: `pip install huggingface_hub`.

After completion, point provider to the downloaded file (e.g. set llama.cpp model path to the new GGUF). 

Example provider switch (curl):
```powershell
curl -X POST -H "Content-Type: application/json" -d '{"name":"echo"}' http://127.0.0.1:8000/provider/set
```

## Optional: pre-commit hooks

You can enable formatting and linting pre-commit hooks locally (not enforced in CI yet):

```powershell
pip install pre-commit
pre-commit install
```

This sets up Black, isort, and Flake8 via `.pre-commit-config.yaml`.

## Per-skill sandbox (optional venv)

You can run each skill's tests in an isolated virtual environment. This is off by default to keep CI fast. Enable it via an environment variable and bootstrap the venv once:

```powershell
$env:LOCAL_AGENT_SKILL_VENV = "1"
# Optional bootstrap inside the skill venv (example for a skill named 'word_count')
python - <<'PY'
from src.local_agent.skills.manager import SkillManager
m = SkillManager()
py = m._ensure_skill_venv('word_count')
import subprocess
subprocess.run([str(py), '-m', 'pip', 'install', '--upgrade', 'pip'], check=False)
subprocess.run([str(py), '-m', 'pip', 'install', 'pytest'], check=False)
PY
```

After that, installing a skill with tests and approval will execute those tests in the skill's venv.

Notes:
- The venv is created under `.agent_data/skills/<name>/venv`.
- If pytest is not installed in that venv, test execution will fail with an error. Bootstrap as shown above.
- For strict isolation, you may also install only the minimal dependencies the skill needs into that venv.
