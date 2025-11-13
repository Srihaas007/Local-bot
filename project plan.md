# Local-bot Project Plan (v1)

Date: 2025-11-13
Repo: https://github.com/Srihaas007/Local-bot

## Vision and scope

Build a local, privacy-first personal assistant that runs entirely on your Windows PC (i9, 16GB RAM, RTX 4070 8GB). The assistant can read/write files, run scoped commands with approvals, persist and retrieve memories across sessions, and safely self-extend by proposing new tools ("skills") that include code, tests, and docs for your approval. No cloud APIs are required.

Success criteria:
- Responds to prompts and selectively uses tools with explicit approval gates.
- Persists important facts and retrieves them later (keyword + semantic memory).
- Proposes new skills when missing capabilities, including manifest, implementation, tests, and README; installs only after tests pass and user approval.
- All changes are versioned, tested, and auditable; CI runs on each push/PR.

## Architecture overview

- Agent loop: ReAct-style with a JSON tool-call protocol.
  - Reply: `{ "type": "reply", "content": "..." }`
  - Tool: `{ "type": "tool", "name": "...", "args": { ... } }`
- Model providers (no Ollama required):
  - EchoProvider (tests only).
  - LlamaCppProvider (GGUF via llama-cpp-python).
  - TransformersProvider (HuggingFace + Torch + optional bitsandbytes 4-bit).
- Tools (path-jail to workspace):
  - read_file, write_file, list_files, shell_run (disabled by default).
- Memory:
  - v1: SQLite keyword store (implemented).
  - v1.1: Semantic memory via embeddings + vector search (SQLite VSS or Chroma).
  - Summarization + retention policies.
- Safety:
  - Workspace path jail; network tools off by default (explicit enable).
  - Approval gate for tool runs; kill-switch and max-steps for loops.
- CI:
  - GitHub Actions run pytest on Windows + Ubuntu (Python 3.10).
- Optional orchestration:
  - LangGraph-based multi-step workflows with retries and guardrails (Phase 2).

## Milestones

M0 (DONE): Bootstrap
- Deliverables: Repo scaffold, CLI, providers, tools, SQLite memory, tests, CI.
- Status: Completed and pushed to main.

M1: Semantic memory and retrieval (2–3 days)
- Deliverables:
  - Embeddings via sentence-transformers (all-MiniLM-L6-v2 or bge-small).
  - Vector store: SQLite VSS if available; fallback to local Chroma.
  - Memory API: add(kind, text, importance?), retrieve(query, k, filters).
  - Policies: dedupe, TTL, periodic summarization job.
- Tasks:
  - Add embeddings provider abstraction.
  - Implement vector storage and retrieval blending (recency + semantic + importance).
  - Integrate top-k memory into agent context per step.
  - Tests: retrieval accuracy on synthetic notes; performance smoke on CPU.
- Acceptance:
  - Agent recalls facts across sessions without re-reading files.
  - Query-to-memory latency < 500ms on CPU for small DB.
- Risks: Windows wheels for some libs; mitigation: CPU-friendly models first.

M2: Skill factory (self-extend safely) (3–5 days)
- Deliverables:
  - Skill manifest schema (name, description, inputs/outputs, permissions).
  - Generator: agent proposes manifest + implementation + unit tests + README.
  - Sandbox runner: per-skill venv, timeouts, resource limits.
  - Approval UI: diffs + test results before install.
  - Registry: `skills/` with versioning and status (installed/disabled).
- Tasks:
  - Define schema + interfaces for skills.
  - Implement generation flow: plan → code → tests → run tests → present results.
  - Installer/uninstaller with git tags and pinned deps.
  - Tests: golden tests for "word_count" and "web_fetch" (network gated).
- Acceptance:
  - On missing capability, agent can propose and install a new tool after passing tests and explicit approval.
- Risks: Dependency conflicts; mitigation: per-skill venv and pinned requirements.

M3: Advanced tools and guardrails (3–4 days)
- Deliverables:
  - web_fetch (requests with domain allowlist, size/time limits).
  - run_python in jailed temp dir (no network, resource caps).
  - git ops tool (diff, commit) with approval.
  - Prompt-injection defenses via provenance tagging.
- Tasks:
  - Implement web_fetch with MIME filters and robots compliance.
  - Implement run_python with ephemeral workspace and strict limits.
  - Add git tool via subprocess; require approval before commit.
  - Annotate prompts with provenance for untrusted content/memory.
- Acceptance:
  - Tools operate within limits and fail safely; risky actions require approval.
- Risks: Prompt injection from web; mitigated by provenance + allowlists.

M4: Orchestration and UX (3–5 days)
- Deliverables:
  - LangGraph orchestration for multi-step flows, retries, kill-switch.
  - Minimal UI (Streamlit or Textual TUI) to show trace, diffs, memory hits, approvals.
- Tasks:
  - Model loop as graph: plan → retrieve → act → validate → loop (bounded).
  - Implement retries/backoff; watchdog for runaway loops.
  - Build thin UI for control and visibility.
- Acceptance:
  - Complex tasks run as deterministic graphs with clear logs and control.
- Risks: Scope creep; keep UI focused on approvals and visibility.

M5: Hardening, benchmarks, docs (2–3 days)
- Deliverables:
  - Benchmarks: latency, VRAM/CPU usage, small task-suite success rates.
  - Security defaults reviewed; risky tools default-off.
  - Full docs: setup, models, skills, memory, safety, troubleshooting.
- Tasks:
  - Add sample tasks: multi-file refactor, note recall, web research with citations.
  - Measure with llama.cpp (GGUF) and Transformers 4-bit on RTX 4070.
  - Troubleshooting guide for Windows GPU/driver/model issues.
- Acceptance:
  - Reproducible runs, documented baselines, and clear safety defaults.

## Detailed components

Model providers
- llama-cpp-python: expose `n_threads`, `n_gpu_layers`, context; prompt templates.
- Transformers: 4-bit quant, `device_map=auto`, token streaming; context sizing.
- Optional: streaming interface for incremental token printing in CLI.

Memory
- Schema: `id, ts, kind, text, embedding (nullable), importance, tags`.
- Summarizer: nightly or on-demand compression of long histories.
- Export/import: JSONL for portability.

Tools API
- Structured JSON schemas and validation.
- Capability gating via flags and allowlists.
- Telemetry: JSONL trace of tool calls/outcomes for observability.

Safety/governance
- Path allowlist + forbidden patterns; path jail enforced.
- Network allowlist; max content length; MIME checks.
- Kill-switch + max-steps with clear user prompts.

Testing
- Unit tests for providers, tools, memory, parser.
- Integration tests for end-to-end scripted tasks.
- Golden files for stable prompts and expected artifacts.

CI/CD
- Pytest on push/PR across Windows/Ubuntu.
- Cache pip dirs for speed.
- Optional: pre-commit (black, isort, ruff/flake8) locally.

Docs
- README sections per feature; architecture and flow diagrams.
- "How to add a skill" walkthrough with screenshots/CLI examples.

## Hardware-aware configurations

- llama.cpp (recommended first):
  - Model: Llama 3.1 8B Instruct GGUF Q4_K_M; context ~4k; temp 0.2; top_p 0.9.
  - CUDA build optional; set `n_gpu_layers` to offload; fallback CPU is fine for testing.
- Transformers (alternative):
  - Install Torch CUDA per pytorch.org; use bitsandbytes 4-bit.
  - `device_map=auto`; `max_new_tokens ~512` for CLI; monitor VRAM.
- Embeddings:
  - CPU first (small models); cache embeddings on disk; small batch sizes.

## Risk register

- Windows package friction (bitsandbytes/CUDA): Start with llama.cpp; add Transformers later.
- Prompt injection/unsafe actions: provenance tags, approvals, allowlists, kill-switch.
- Model quality vs speed: begin with 8B; consider better quantization; swap models per task.
- Dependency drift in skills: per-skill venv + pinned requirements + tests.

## Timeline (estimates)

- Week 1: M1 (semantic memory) complete; start M2 scaffolding.
- Week 2: Finish M2; ship M3 web_fetch/run_python basic; stabilize.
- Week 3: M4 orchestration + thin UI; M5 hardening and docs.

## Definition of Done (feature-level)

- Functionality implemented with tests (unit + 1–2 integration cases).
- Safety gates and approvals wired where applicable.
- Docs updated: usage, configuration, and troubleshooting.
- CI green on Windows + Ubuntu.

## Quality gates

- Build/Install: project installs in a clean venv; pinned optional heavy deps.
- Lint/Typecheck: optional pre-commit locally; CI focuses on tests to keep friction low.
- Tests: stable and reproducible; avoid network in tests unless explicitly mocked/gated.

## Next steps

1) Implement M1 semantic memory:
   - Add sentence-transformers (optional install) and a vector store.
   - Wire retrieval into agent context; write tests.
2) Decide default model path:
   - GGUF via llama.cpp (recommended to start) or Transformers 4-bit.
3) Begin M2 skill factory scaffolding:
   - Define skill schema and sandbox runner; add first demo skill.

Once you confirm, we’ll start M1 and push incremental PRs with tests and docs.
