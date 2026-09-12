"""
Connection and per-role settings, read from config.toml.

Both harnesses talk to any OpenAI-compatible /v1/chat/completions endpoint —
Ollama, llama.cpp's server, vLLM, LM Studio, etc. all expose this. No SDK
dependency (plain stdlib urllib + tomllib) so these scripts run with nothing
beyond a standard Python 3.11+ install.

config.toml lives alongside the entrypoint scripts, one level up from this
file:

    llm_url = "http://localhost:11434/v1"
    # api_key = "local"   # optional, most local servers ignore it

    [planner]
    model = "qwen3:14b"
    temperature = 0.4
    num_ctx = 16384

    [architect]
    model = "qwen2.5:14b"
    temperature = 0.3
    num_ctx = 16384

Separate [planner]/[architect] sections exist specifically so you can run
different models or sampling settings per role while experimenting.
"""

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    model: str
    temperature: float
    num_ctx: int

    @classmethod
    def load(cls, section: str) -> "Config":
        if not CONFIG_PATH.exists():
            print(
                f"Error: config file not found at {CONFIG_PATH}\n"
                f"Create it with at least an llm_url and a [{section}] section — "
                f"see harness/config.py's docstring for the format.",
                file=sys.stderr,
            )
            sys.exit(1)

        with open(CONFIG_PATH, "rb") as f:
            try:
                data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                print(f"Error: could not parse {CONFIG_PATH}: {e}", file=sys.stderr)
                sys.exit(1)

        base_url = data.get("llm_url")
        if not base_url:
            print(f"Error: '{CONFIG_PATH}' is missing top-level 'llm_url'.", file=sys.stderr)
            sys.exit(1)
        base_url = base_url.rstrip("/")

        api_key = data.get("api_key", "local")

        if section not in data:
            print(
                f"Error: '{CONFIG_PATH}' has no [{section}] section.\n"
                f"Add one with at least a 'model' key.",
                file=sys.stderr,
            )
            sys.exit(1)

        section_data = data[section]
        model = section_data.get("model")
        if not model:
            print(f"Error: [{section}] section in '{CONFIG_PATH}' is missing 'model'.", file=sys.stderr)
            sys.exit(1)

        temperature = float(section_data.get("temperature", 0.4))
        num_ctx = int(section_data.get("num_ctx", 16384))

        return cls(base_url=base_url, api_key=api_key, model=model,
                    temperature=temperature, num_ctx=num_ctx)
