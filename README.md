# development-agents

Two local, LLM-backed CLI tools — a **Project Planner** and a **Software Architect** —
implementing a learning-first development workflow: they help you scope and understand
a personal software project one task at a time, without ever writing implementation
code for you. See [`workflow.md`](./workflow.md) for the full reasoning behind how these
two roles work and why they're split the way they are. This README covers installing
and running the tools themselves.

Both tools talk to any local, OpenAI-compatible chat completions server that supports
tool/function calling — Ollama, llama.cpp's server, vLLM, and LM Studio all qualify.

## Requirements

- Python 3.11+ (uses `tomllib` from the standard library)
- [`uv`](https://docs.astral.sh/uv/)
- `git`
- A local LLM server exposing an OpenAI-compatible `/v1/chat/completions` endpoint, with
  a model that supports tool/function calling
- `less` on PATH (optional — used to page long responses; the tools fall back to plain
  output if it isn't found)

## Install

From inside this repository:

```bash
uv tool install --editable .
```

**Use `--editable`, not a plain install.** The tools locate `config.toml` relative to
their own source location on disk. An editable install keeps that pointing at this
repository's actual `src/development_agents/config.toml`; a normal (non-editable)
install copies the package into an isolated environment where that file generally won't
exist, since it's meant to be edited locally rather than bundled as shipped package
data.

This puts `project-planner` and `software-architect` on your PATH, runnable from
anywhere — which matters, since you'll typically invoke them from wherever you keep your
actual projects, not from inside this repository.

*(If your `pyproject.toml` doesn't declare these as console script entry points yet, add
them under `[project.scripts]` pointing at `development_agents.project_planner:main` and
`development_agents.software_architect:main` respectively.)*

## Configure

Edit `src/development_agents/config.toml`:

```toml
llm_url = "http://localhost:11434/v1"
# api_key = "local"   # optional — most local servers ignore this

[planner]
model = "qwen3:14b"
temperature = 0.4
num_ctx = 16384

[architect]
model = "qwen2.5:14b"
temperature = 0.3
num_ctx = 16384
```

`llm_url` is shared between both tools. `[planner]` and `[architect]` are separate
sections specifically so you can run different models or sampling settings per role.
Both models need to support tool/function calling in their chat template — if a tool
call never fires (a project never gets created, a task never gets started), that's
usually a model capability issue rather than a bug in these scripts.

## Usage

```bash
# One-time, when starting a new project. Run from wherever you keep your projects —
# this creates ./dino-game relative to your current directory.
project-planner dino-game

# Every session after that, from the same location.
software-architect dino-game
```

Each command assumes the project name resolves relative to your current working
directory. See `workflow.md` for what actually happens during each session and what
gets created inside the target project's directory.

## Project Structure (this repository)

```
development-agents/
  pyproject.toml
  pyrightconfig.json
  uv.lock
  README.md
  workflow.md
  src/
    development_agents/
      config.toml                     # edit this — see Configure, above
      py.typed
      __init__.py
      project_planner.py               # entrypoint: project-planner
      software_architect.py             # entrypoint: software-architect
      harness/
        __init__.py
        bootstrap.py                    # the Planner's one hardcoded action
        chat_loop.py                     # shared interactive tool-calling loop (rich-based UI)
        config.py                         # reads config.toml
        fs_tools.py                        # scoped filesystem access (project/ only)
        git_tools.py                        # commit/history helpers
        llm_client.py                        # stdlib HTTP client for the LLM server
        task_tools.py                          # task state detection + task creation
      prompts/
        planner_system_prompt.md
        architect_system_prompt.md
```

Do not confuse this structure with the structure of a project you *build* using these
tools (e.g. `dino-game/`) — that's a separate directory elsewhere on disk, created by
`project-planner`, and is covered in `workflow.md`.

## Notes and Known Limitations

- There is no conversation persistence between runs — closing the terminal ends that
  session's chat. Durable state is only whatever has been written under the target
  project's `project/` directory and committed to git.
- Tool-calling reliability varies significantly across local models, especially below
  ~14B parameters. If a session talks normally but never seems to call its tools (no
  project gets created, no task gets started), try a different model before assuming
  the harness is broken.
- The Architect's read/write access is scoped in code to the target project's `project/`
  directory — it cannot reach `src/` even if asked. This is enforced by
  `harness/fs_tools.py`, not by the system prompt alone.
