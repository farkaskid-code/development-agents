"""
Generic interactive tool-calling loop.

Both harnesses are: a system prompt, a small tool registry, and this loop.
Nothing persona-specific lives here.

Uses `rich` for output — the model's markdown (headers, code fences, bold,
lists) renders properly instead of printing as literal `**`/backtick
characters, and turns are visually separated so a long teaching
conversation stays scannable. This is the one non-stdlib dependency in the
project: `pip install rich`.
"""

import io
import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from . import llm_client
from .config import Config

console = Console()


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema for the function's parameters
    fn: Callable[..., dict]
    ends_session: bool = False  # e.g. bootstrap_project — one-shot, then exit

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _render_to_ansi_text(panel: Panel) -> str:
    """Renders a panel to a plain string with ANSI codes intact, regardless
    of whether the real stdout is a TTY — used to hand content to `less`."""
    buffer = io.StringIO()
    capture_console = Console(
        file=buffer,
        force_terminal=True,
        width=console.width,
        color_system="truecolor",
    )
    capture_console.print(panel)
    return buffer.getvalue()


def _print_assistant(text: str, label: str) -> None:
    """
    Prints the assistant's response in a bordered markdown panel, labeled
    with the current persona's name (so the Planner doesn't show up as
    "Architect" and vice versa).

    If the rendered panel is taller than the terminal, it's shown through
    `less` instead of dumped straight to scrollback — conditional, not
    automatic for every reply, so short answers don't force a `q` press for
    no reason.

    Uses `less -RFX` directly rather than rich's built-in `console.pager()`
    helper: specifically the `-X` flag, which stops `less` from switching to
    the alternate screen buffer. Without it, quitting the pager restores the
    terminal to exactly how it looked before — the content you just paged
    through never actually lands in your scrollback. `-X` keeps it there,
    so you can still scroll back up to reread it after quitting.
    """
    if not text:
        return

    panel = Panel(
        Markdown(text),
        title=label,
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    )

    render_options = console.options.update(width=console.width)
    rendered_line_count = len(console.render_lines(panel, render_options))
    available_height = max(console.size.height - 4, 5)

    if rendered_line_count <= available_height:
        console.print(panel)
        return

    if shutil.which("less") is None:
        # No pager available on this system — fall back to a plain print
        # rather than failing.
        console.print(panel)
        return

    console.print(
        "[dim](long response — opening pager, press q to return; "
        "stays in scrollback after)[/dim]"
    )
    rendered = _render_to_ansi_text(panel)
    subprocess.run(["less", "-RFX"], input=rendered, text=True)


def _print_tool_call(name: str, args: dict) -> None:
    arg_preview = ", ".join(
        f"{k}=..." if isinstance(v, str) and len(v) > 40 else f"{k}={v!r}"
        for k, v in args.items()
    )
    console.print(f"[dim]  → {name}({arg_preview})[/dim]")


def _print_tool_result(name: str, result: dict) -> None:
    status = result.get("status", "ok") if isinstance(result, dict) else "ok"
    style = "green" if status == "ok" else "red"
    console.print(f"[{style}]  ↳ {status}[/{style}]")


def run_chat_loop(
    config: Config,
    system_prompt: str,
    tools: dict[str, ToolSpec],
    context_messages: list[dict] | None = None,
    opening_line: str | None = None,
    assistant_label: str = "Assistant",
) -> None:
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if context_messages:
        messages.extend(context_messages)

    if opening_line:
        console.print()
        console.print(Rule(style="dim"))
        console.print(f"[bold]{opening_line}[/bold]")
        console.print(Rule(style="dim"))

    tool_schemas = [t.schema() for t in tools.values()] if tools else None

    while True:
        try:
            console.print()
            user_input = console.input("[bold blue]You:[/bold blue] ").strip()
        except EOFError, KeyboardInterrupt:
            console.print("\n[dim]Session ended.[/dim]")
            return

        if user_input.lower() in ("exit", "quit"):
            console.print("[dim]Session ended.[/dim]")
            return
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        session_should_end = False

        # Inner loop: keep resolving tool calls until the model returns a
        # plain text response with nothing left to call.
        while True:
            try:
                with console.status("[dim]thinking...[/dim]", spinner="dots"):
                    assistant_msg = llm_client.chat(
                        config, messages, tools=tool_schemas
                    )
            except llm_client.LLMError as e:
                console.print(f"[bold red][LLM error][/bold red] {e}")
                break

            messages.append(assistant_msg)
            tool_calls = assistant_msg.get("tool_calls")

            if not tool_calls:
                _print_assistant(assistant_msg.get("content", ""), assistant_label)
                break

            for call in tool_calls:
                fn_name = call["function"]["name"]
                raw_args = call["function"].get("arguments", "{}")
                try:
                    args = (
                        json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    )
                except json.JSONDecodeError:
                    args = {}

                _print_tool_call(fn_name, args)

                spec = tools.get(fn_name)
                if spec is None:
                    result = {"status": "error", "message": f"Unknown tool '{fn_name}'"}
                else:
                    try:
                        result = spec.fn(**args)
                    except (
                        Exception
                    ) as e:  # surface to the model, don't crash the session
                        result = {"status": "error", "message": str(e)}
                    if spec.ends_session:
                        session_should_end = True

                _print_tool_result(fn_name, result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", fn_name),
                        "name": fn_name,
                        "content": json.dumps(result),
                    }
                )
            # loop back: let the model see the tool result(s) and respond

        if session_should_end:
            console.print("[bold]Session complete.[/bold]")
            return
