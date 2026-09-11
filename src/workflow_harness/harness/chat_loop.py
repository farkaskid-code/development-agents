"""
Generic interactive tool-calling loop.

Both harnesses are: a system prompt, a small tool registry, and this loop.
Nothing persona-specific lives here.
"""

import json
from dataclasses import dataclass
from typing import Any, Callable

from . import llm_client
from .config import Config


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


def _print_assistant(text: str) -> None:
    if text:
        print(f"\nArchitect: {text}\n")


def run_chat_loop(
    config: Config,
    system_prompt: str,
    tools: dict[str, ToolSpec],
    context_messages: list[dict] | None = None,
    opening_line: str | None = None,
) -> None:
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if context_messages:
        messages.extend(context_messages)

    if opening_line:
        print(f"\n{opening_line}\n")

    tool_schemas = [t.schema() for t in tools.values()] if tools else None

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            return

        if user_input.lower() in ("exit", "quit"):
            print("Session ended.")
            return
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        session_should_end = False

        # Inner loop: keep resolving tool calls until the model returns a
        # plain text response with nothing left to call.
        while True:
            try:
                assistant_msg = llm_client.chat(config, messages, tools=tool_schemas)
            except llm_client.LLMError as e:
                print(f"\n[LLM error] {e}\n")
                break

            messages.append(assistant_msg)
            tool_calls = assistant_msg.get("tool_calls")

            if not tool_calls:
                _print_assistant(assistant_msg.get("content", ""))
                break

            for call in tool_calls:
                fn_name = call["function"]["name"]
                raw_args = call["function"].get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}

                spec = tools.get(fn_name)
                if spec is None:
                    result = {"status": "error", "message": f"Unknown tool '{fn_name}'"}
                else:
                    try:
                        result = spec.fn(**args)
                    except Exception as e:  # surface to the model, don't crash the session
                        result = {"status": "error", "message": str(e)}
                    if spec.ends_session:
                        session_should_end = True

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", fn_name),
                    "name": fn_name,
                    "content": json.dumps(result),
                })
            # loop back: let the model see the tool result(s) and respond

        if session_should_end:
            print("Session complete.")
            return
