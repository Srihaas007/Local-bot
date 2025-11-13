from __future__ import annotations
import sys
import textwrap
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from ..config import WORKSPACE
from .base import Tool, ToolResult


SANDBOX_ROOT = WORKSPACE / ".agent_data" / "sandboxes"
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(WORKSPACE))
    except Exception:
        return str(p)


class RunPython(Tool):
    name = "run_python"
    description = (
        "Run a Python snippet in a temporary sandbox directory under the workspace. "
        "Enforces a timeout and optional restricted I/O (default true)."
    )

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to run"},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "timeout": {"type": "integer", "default": 10},
                    "restricted": {"type": "boolean", "default": True},
                    "keep": {"type": "boolean", "default": False},
                    "stdin": {"type": "string", "default": ""},
                },
                "required": ["code"],
            },
        }

    def _make_prelude(self, sandbox: Path, restricted: bool) -> str:
        if not restricted:
            return ""
        # Restrict imports and I/O to within sandbox where possible.
        # This is a best-effort guard; not a hardened sandbox.
        return textwrap.dedent(
            f"""
            import builtins, os, io, pathlib, sys
            from pathlib import Path

            _SANDBOX = Path(r"{sandbox.as_posix()}").resolve()

            _orig_open = builtins.open
            def _safe_open(file, *args, **kwargs):
                # Allow file descriptors and in-memory files
                if isinstance(file, int) or isinstance(file, io.IOBase):
                    return _orig_open(file, *args, **kwargs)
                p = Path(file)
                if not p.is_absolute():
                    p = (Path.cwd() / p).resolve()
                else:
                    p = p.resolve()
                if not str(p).startswith(str(_SANDBOX)):
                    raise PermissionError(f"Access outside sandbox: {{p}}")
                return _orig_open(p, *args, **kwargs)

            builtins.open = _safe_open

            _orig_path_open = pathlib.Path.open
            def _safe_path_open(self, *args, **kwargs):
                p = self
                if not p.is_absolute():
                    p = (Path.cwd() / p).resolve()
                else:
                    p = p.resolve()
                if not str(p).startswith(str(_SANDBOX)):
                    raise PermissionError(f"Access outside sandbox: {{p}}")
                return _orig_path_open(p, *args, **kwargs)
            pathlib.Path.open = _safe_path_open

            # Disallow a handful of dangerous modules by stub
            class _Blocker:
                def __getattr__(self, name):
                    raise ImportError("Module is blocked in restricted mode")

            for _mod in ("subprocess", "socket", "ctypes", "multiprocessing"):
                sys.modules[_mod] = _Blocker()
            """
        )

    def run(self, **kwargs: Any) -> ToolResult:
        code: str = kwargs.get("code", "")
        args: List[str] = list(kwargs.get("args", []))
        timeout: int = int(kwargs.get("timeout", 10))
        restricted: bool = bool(kwargs.get("restricted", True))
        keep: bool = bool(kwargs.get("keep", False))
        stdin_str: str = str(kwargs.get("stdin", ""))

        if not code.strip():
            return ToolResult(ok=False, content="No code provided")

        sandbox = SANDBOX_ROOT / str(uuid.uuid4())
        try:
            sandbox.mkdir(parents=True, exist_ok=True)
            main_py = sandbox / "main.py"
            prelude = self._make_prelude(sandbox, restricted)
            main_py.write_text(prelude + "\n" + code, encoding="utf-8")

            cmd = [sys.executable, "-I", "-B", str(main_py.name), *args]
            started = time.time()
            proc = subprocess.run(
                cmd,
                cwd=sandbox,
                input=stdin_str,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.time() - started
            ok = proc.returncode == 0
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            details = f"exit={proc.returncode} time={elapsed:.2f}s sandbox={_rel(sandbox)}"
            if ok:
                content = stdout if stdout else "(no output)"
                if keep:
                    content = content + "\n" + details
                return ToolResult(ok=True, content=content)
            else:
                msg = stderr if stderr else "Python exited with non-zero code"
                if keep:
                    msg = msg + "\n" + details
                return ToolResult(ok=False, content=msg)
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, content=f"Timeout after {timeout}s")
        except Exception as e:
            return ToolResult(ok=False, content=f"run_python error: {e}")
        finally:
            if not keep:
                try:
                    # Best-effort cleanup
                    for p in sorted(sandbox.rglob("*"), reverse=True):
                        try:
                            if p.is_file() or p.is_symlink():
                                p.unlink(missing_ok=True)
                            elif p.is_dir():
                                p.rmdir()
                        except Exception:
                            pass
                    sandbox.rmdir()
                except Exception:
                    pass
