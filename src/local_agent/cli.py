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
@click.option("--no-stream", is_flag=True, default=False, help="Disable token streaming in CLI")
def main(provider: str, model_path: str | None, model_name: str | None, allow_shell: bool, no_approve: bool, no_stream: bool) -> None:
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
        if no_stream:
            result = agent.step(user)
            if result.used_tool and result.output.startswith("Tool requested:"):
                console.print(result.output)
                pending_tool = result.used_tool
            else:
                console.print(result.output)
        else:
            # Stream tokens when possible. Agent.step_stream yields chunks and returns an AgentResult at the end.
            last_result = None
            for chunk in agent.step_stream(user):
                # step_stream yields strings; the last return is handled via the generator's StopIteration value, but we also yield messages for prompts
                console.print(chunk, end="")
            # After streaming, we re-run a minimal parse by calling step with approve=None? No: step_stream already appended history.
            # To reflect any trailing messages (like tool approvals), we call step_stream again isn't needed; Instead, the last yielded lines include prompts.
            # For simplicity, read the last history message to decide if a tool was requested.
            # We fallback to asking approval on next loop if we detect the standard text.
            # Detect pending action set by step_stream
            if getattr(agent, "_pending_action", None) is not None:
                pending_tool = agent._pending_action.get("name")  # type: ignore
            console.print("")


if __name__ == "__main__":
    main()
