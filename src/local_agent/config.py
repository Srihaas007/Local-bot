from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.getenv("LOCAL_AGENT_ROOT", Path(__file__).resolve().parents[2]))
WORKSPACE = ROOT  # Path jail root; by default the repo root
MEMORY_DB = ROOT / ".agent_data" / "memory.sqlite3"
MODELS_DIR = ROOT / "models"

os.makedirs(MEMORY_DB.parent, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

@dataclass
class RuntimeFlags:
    allow_shell: bool = False
    approve_tools: bool = True
    allowed_domains: tuple[str, ...] = ()
    skill_venv: bool = False  # Run skill tests in per-skill virtualenv (optional)

FLAGS = RuntimeFlags(
    allow_shell=os.getenv("LOCAL_AGENT_ALLOW_SHELL", "0") == "1",
    approve_tools=os.getenv("LOCAL_AGENT_APPROVE_TOOLS", "1") == "1",
    allowed_domains=tuple(filter(None, (os.getenv("LOCAL_AGENT_ALLOWED_DOMAINS", "").split(",")))),
    skill_venv=os.getenv("LOCAL_AGENT_SKILL_VENV", "0") == "1",
)
