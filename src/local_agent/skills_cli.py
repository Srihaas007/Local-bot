from __future__ import annotations
import json
from pathlib import Path
import click
from rich.console import Console
from .skills.manager import SkillManager, SKILLS_DIR, GENERATED_TOOLS_DIR
from .skills.schema import SkillManifest

console = Console()

@click.group()
def main() -> None:
    """Skills CLI: manage Local-bot skills (tools)."""
    pass

@main.command("list")
def list_skills() -> None:
    """List installed skills (manifests) and generated tools."""
    console.print("[bold]Skills (manifests)[/bold]")
    for p in sorted((SKILLS_DIR).glob("*/manifest.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            console.print(f"- {p.parent.name}: {data.get('description','')} ")
        except Exception:
            console.print(f"- {p.parent.name}: (invalid manifest)")
    console.print("\n[bold]Generated tools[/bold]")
    if GENERATED_TOOLS_DIR.exists():
        for p in sorted(GENERATED_TOOLS_DIR.glob("*.py")):
            if p.name == "__init__.py":
                continue
            console.print(f"- {p.stem}")
    else:
        console.print("(none)")

@main.command("install")
@click.option("--manifest", "manifest_path", type=click.Path(exists=True, dir_okay=False), required=True, help="Path to manifest.json")
@click.option("--code", "code_path", type=click.Path(exists=True, dir_okay=False), required=True, help="Path to tool implementation .py")
@click.option("--tests", "tests_path", type=click.Path(exists=True, dir_okay=False), required=False, help="Optional path to pytest file for the skill")
@click.option("--auto-approve", is_flag=True, default=False, help="Install without interactive approval prompt")
@click.option("--run-tests", is_flag=True, default=True, help="Run the provided tests after install")
def install_skill(manifest_path: str, code_path: str, tests_path: str | None, auto_approve: bool, run_tests: bool) -> None:
    """Install a skill from files (manifest.json, code.py, optional tests)."""
    m_path = Path(manifest_path)
    c_path = Path(code_path)
    t_path = Path(tests_path) if tests_path else None
    manifest_data = json.loads(m_path.read_text(encoding="utf-8"))
    manifest = SkillManifest(**manifest_data)

    summary = {
        "name": manifest.name,
        "description": manifest.description,
        "permissions": manifest.permissions,
        "inputs": manifest.inputs,
        "outputs": manifest.outputs,
        "code": str(c_path),
        "tests": str(t_path) if t_path else None,
    }
    console.print("[bold]Install skill[/bold]", summary)

    if not auto_approve:
        if not click.confirm("Proceed with installation?", default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    mgr = SkillManager()
    tool_code = c_path.read_text(encoding="utf-8")
    test_code = t_path.read_text(encoding="utf-8") if t_path else None
    try:
        mgr.install_skill(manifest, tool_code, test_code, approve=bool(run_tests and test_code))
        console.print(f"[green]Installed skill '{manifest.name}'.[/green]")
    except Exception as e:
        console.print(f"[red]Installation failed:[/red] {e}")
        raise SystemExit(1)

@main.command("run-tests")
@click.option("--path", type=str, default="tests/skills", help="Run pytest on this path")
def run_tests(path: str) -> None:
    import subprocess
    cmd = ["python", "-m", "pytest", "-q", path]
    console.print(f"Running tests: {' '.join(cmd)}")
    proc = subprocess.run(cmd, text=True)
    raise SystemExit(proc.returncode)

if __name__ == "__main__":
    main()
