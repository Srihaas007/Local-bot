from __future__ import annotations
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ..config import ROOT, FLAGS
from ..tools.base import Tool
from .schema import SkillManifest

SKILLS_DIR = ROOT / "skills"
GENERATED_TOOLS_DIR = ROOT / "src" / "local_agent" / "tools" / "generated"

for d in (SKILLS_DIR, GENERATED_TOOLS_DIR):
    d.mkdir(parents=True, exist_ok=True)


class SkillManager:
    def __init__(self, repo_root: Path = ROOT):
        self.root = repo_root

    def install_skill(self, manifest: SkillManifest, tool_code: str, test_code: Optional[str] = None, approve: bool = True) -> Path:
        """
        Install a new skill by writing its manifest, tool code, and optional tests.
        Returns the path to the installed tool module.
        """
        name = manifest.name
        if not name.isidentifier():
            raise ValueError("Skill name must be a valid identifier (python).")

        # Write manifest under skills/<name>/manifest.json
        sdir = SKILLS_DIR / name
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

        # Write tool under tools/generated/<name>.py
        tool_path = GENERATED_TOOLS_DIR / f"{name}.py"
        tool_path.write_text(tool_code, encoding="utf-8")

        # Ensure generated __init__ exists and imports all
        init_path = GENERATED_TOOLS_DIR / "__init__.py"
        if not init_path.exists():
            init_path.write_text("__all__ = []\n", encoding="utf-8")
        # Append export line if not present
        init_txt = init_path.read_text(encoding="utf-8")
        export_line = f"from .{name} import {self._tool_class_name(name)}\n"
        if export_line not in init_txt:
            init_txt += export_line
            # Keep a simple __all__ maintenance (best-effort)
            if "__all__" not in init_txt:
                init_txt = f"__all__ = []\n{init_txt}"
            if "__all__.append" not in init_txt:
                init_txt += f"__all__.append('{self._tool_class_name(name)}')\n"
            else:
                init_txt += f"__all__.append('{self._tool_class_name(name)}')\n"
            init_path.write_text(init_txt, encoding="utf-8")

        # Write test if provided
        if test_code:
            tdir = self.root / "tests" / "skills"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / f"test_{name}.py").write_text(test_code, encoding="utf-8")

        # Optionally run tests for just this skill (approval gate simulated here)
        if approve and test_code:
            self._run_pytest_subset(f"tests/skills/test_{name}.py")

        return tool_path

    def _run_pytest_subset(self, path: str) -> None:
        # Run pytest on a subset; optionally in a per-skill venv
        if FLAGS.skill_venv:
            # Infer skill name from test file path: tests/skills/test_<name>.py
            try:
                skill_name = Path(path).stem.replace("test_", "", 1)
            except Exception:
                skill_name = "skill"
            py = self._ensure_skill_venv(skill_name)
            cmd = [str(py), "-m", "pytest", "-q", path]
        else:
            cmd = ["python", "-m", "pytest", "-q", path]
        proc = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Skill tests failed:\n{proc.stdout}\n{proc.stderr}")

    def _ensure_skill_venv(self, name: str) -> Path:
        """Create or reuse a virtualenv for a given skill; returns python executable path."""
        vroot = self.root / ".agent_data" / "skills" / name
        venv_dir = vroot / "venv"
        venv_dir.mkdir(parents=True, exist_ok=True)
        # Create venv if not initialized (pyvenv.cfg absent)
        if not (venv_dir / "pyvenv.cfg").exists():
            c = subprocess.run(["python", "-m", "venv", str(venv_dir)], cwd=self.root, capture_output=True, text=True)
            if c.returncode != 0:
                raise RuntimeError(f"Failed to create venv for skill '{name}':\n{c.stdout}\n{c.stderr}")
        # Resolve python path
        win_py = venv_dir / "Scripts" / "python.exe"
        nix_py = venv_dir / "bin" / "python"
        if win_py.exists():
            return win_py
        if nix_py.exists():
            return nix_py
        # Fallback
        return nix_py

    @staticmethod
    def _tool_class_name(name: str) -> str:
        # Convert snake_case to PascalCase + 'Tool'
        parts = name.split("_")
        return "".join(p.capitalize() for p in parts) + "Tool"
