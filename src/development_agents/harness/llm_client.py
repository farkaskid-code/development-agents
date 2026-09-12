"""
Minimal OpenAI-compatible chat client using only the standard library.

Deliberately not using the `openai` SDK: this is a small, personal tool, and
avoiding the dependency means it runs on a bare `python3` with nothing to
install. Any local server exposing /v1/chat/completions with tool-calling
support in the OpenAI wire format works (Ollama, llama.cpp server, vLLM,
LM Studio).
"""

import json
import urllib.error
import urllib.request
from typing import Any

from .config import Config


class LLMError(RuntimeError):
    pass


def chat(config: Config, messages: list[dict], tools: list[dict] | None = None) -> dict[str, Any]:
    """
    Send a chat completion request. Returns the assistant message dict as
    given by the API, e.g.:
        {"role": "assistant", "content": "...", "tool_calls": [...]}
    tool_calls is omitted/None if the model didn't call a tool.
    """
    body: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "stream": False,
        # Not every backend honors this, but Ollama and llama.cpp both do —
        # worth setting explicitly since local servers often default low.
        "options": {"num_ctx": config.num_ctx},
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise LLMError(f"LLM server returned HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise LLMError(
            f"Could not reach LLM server at {config.base_url}: {e.reason}\n"
            "Is your local server running?"
        ) from e

    try:
        return payload["choices"][0]["message"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected response shape from LLM server: {payload}") from e
