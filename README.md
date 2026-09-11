# Local AI-Assisted Development Harnesses

Two standalone CLI tools implementing the Project Planner / Software Architect roles
from the workflow doc. Zero external dependencies — stdlib Python 3.10+ only, so
nothing to `pip install`. Talks to any local OpenAI-compatible server (Ollama,
llama.cpp server, vLLM, LM Studio).

## Setup

Edit `config.toml` (lives next to the entrypoint scripts):

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

`llm_url` is shared; `[planner]` and `[architect]` are separate sections specifically so
you can run different models or sampling settings per role while experimenting. Both
models must support tool/function calling in their chat template.

Requires `git` and `uv` on PATH (`uv` is used by the bootstrap step to `uv init` the
project — swap `harness/bootstrap.py` if you'd rather use something else).

## Usage

```bash
# One-time, per new project. Run from wherever you keep projects.
python3 project_planner.py dino-game

# Every session after that.
python3 software_architect.py dino-game
```

Both assume the project lives at `./{project-name}` relative to your current directory.

## What's here

```
harness/
  config.py        # env-var based LLM connection settings
  llm_client.py     # raw HTTP client for /v1/chat/completions (stdlib only)
  chat_loop.py       # generic tool-calling REPL loop, shared by both scripts
  fs_tools.py          # ScopedFS — hard-enforced read/write boundary to project/
  git_tools.py           # init/commit + history reconstruction & search
  bootstrap.py             # the planner's one hardcoded, non-parameterized action
  task_tools.py              # state detection + start_task for the architect
project_planner.py     # entrypoint: project-planner {project-name}
software_architect.py   # entrypoint: software-architect {project-name}
prompts/
  planner_system_prompt.md
  architect_system_prompt.md
```

## Design notes

- **The Architect can never reach `src/`.** `ScopedFS` resolves every path against its
  root and rejects anything that escapes it — traversal, absolute paths, whatever. This
  is enforced by `fs_tools.py`'s code, not by prompt instruction, so it holds even if a
  model ignores its system prompt.
- **No shell access for the model.** The only mechanical, filesystem/git-touching
  actions (`bootstrap_project`, `start_task`) are fixed Python functions with narrow,
  typed parameters — the model can't ask them to do anything beyond what they're
  written to do.
- **State is detected by the harness, not inferred by the model.** `task_tools.detect_state`
  runs before the chat loop starts; the model is just told the answer.
- **There is no devlog file.** `git log -p` against `task.md`/`report.md`, interleaved
  by commit order, is the devlog. This depends on you squash-merging each task branch
  into exactly one commit on `main` — see the workflow doc for why that discipline
  matters here.
- **No date-guessing.** Every timestamp comes from real git commit metadata instead of
  the model's (often stale) sense of "today."

## Known rough edges to watch for once you're using this for real

- `num_ctx` (from config.toml) is passed via an `options` field aimed at Ollama's API
  shape — if you're running a different backend, check whether it expects
  context-length configuration differently (some servers set this at model-load time
  instead of per-request).
- Tool-calling quality varies a lot across local models, especially <14B ones. If the
  model hallucinates tool arguments or doesn't call tools when it should, that's a model
  capability issue, not a harness bug — worth testing a couple of candidates.
- No conversation persistence between runs — closing the terminal loses that session's
  chat. Durable state is still only what's been written to `project/` and committed.
