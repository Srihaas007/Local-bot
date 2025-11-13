from __future__ import annotations
import click
from rich.console import Console
from .agent import Agent
from .memory import MemoryStore
from .model_providers import EchoProvider

console = Console()


@click.command()
@click.option("--provider", type=click.Choice(["echo", "llamacpp", "transformers"]), default="echo", help="Model provider to use")
@click.option("--model-path", type=str, default=None, help="Path to GGUF (for llamacpp)")
@click.option("--model-name", type=str, default=None, help="HF model name or path (for transformers)")
@click.option("--allow-shell", is_flag=True, default=False, help="Allow shell tool")
@click.option("--no-approve", is_flag=True, default=False, help="Do not ask approval before tool run")
def main(provider: str, model_path: str | None, model_name: str | None, allow_shell: bool, no_approve: bool) -> None:
    # Late import to avoid optional deps at CLI import time
    from .config import FLAGS

    FLAGS.allow_shell = allow_shell
    FLAGS.approve_tools = not no_approve

    if provider == "echo":
        prov = EchoProvider()
    elif provider == "llamacpp":
        from .model_providers.llama_cpp_provider import LlamaCppProvider
        if not model_path:
            console.print("[red]--model-path is required for llamacpp[/red]")
            raise SystemExit(2)
        prov = LlamaCppProvider(model_path=model_path)
    elif provider == "transformers":
        from .model_providers.transformers_provider import TransformersProvider
        if not model_name:
            console.print("[red]--model-name is required for transformers[/red]")
            raise SystemExit(2)
        prov = TransformersProvider(model_name=model_name, device_map="auto", load_in_4bit=True)
    else:
        console.print("[red]Unknown provider[/red]")
        raise SystemExit(2)

    agent = Agent(prov, memory=MemoryStore())

    console.print("[bold]Local Agent[/bold] — type 'exit' to quit.")
    pending_tool: str | None = None
    while True:
        if pending_tool:
            user = console.input("Approve tool? (y/n) > ").strip().lower()
            if user in {"y", "yes"}:
                result = agent.step("(approve)", approve=True)
                console.print(result.output)
            else:
                result = agent.step("(deny)", approve=False)
                console.print(result.output)
            pending_tool = None
            continue

        user = console.input("You > ")
        if user.strip().lower() in {"exit", "quit"}:
            break
        result = agent.step(user)
        if result.used_tool and result.output.startswith("Tool requested:"):
            console.print(result.output)
            pending_tool = result.used_tool
        else:
            console.print(result.output)


if __name__ == "__main__":
    main()
