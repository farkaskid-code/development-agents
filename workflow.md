# Local AI-Assisted Development Process

A learning-first workflow for building side projects with local models, split across
three roles: a **Project Planner** (one-time scoping), a **Software Architect**
(recurring teaching + task design), and a **Companion** (in-editor pairing + review).
The split exists to prevent the usual failure mode of AI-assisted coding — a single
persona collapsing into "just generate the code" the moment you hit something
unfamiliar — and to keep each role's context window matched to how long that
information actually stays relevant.

---

## Philosophy (unchanged from v1)

- Optimize for **understanding**, not just shipping. Code that works but that you
  couldn't reproduce yourself is a failure of this workflow, even if the task is "done."
- The Architect never writes implementation code. The Companion never designs or teaches
  concepts unprompted — it reacts to what you're building.
- State lives in files (and now, git history), not in chat memory. Chat is scratch
  space; anything that should persist gets written down immediately.

---

## Repository Structure

```
project-name/
  project/
    design.md    # durable project state — planner writes once, architect amends
    task.md       # current task's spec only — overwritten each task cycle
    report.md     # current task's devlog entry — template by harness, content by you
  src/
```

Only three files, always current-state-only for `task.md`/`report.md`. There is no
per-task folder and no hand-maintained devlog — **git history against these files is
the devlog.** Because you squash-merge each task branch into a single commit on `main`,
`git log -p -- project/task.md` and `git log -p -- project/report.md`, interleaved by
commit order, reconstruct the full development history: each task's spec followed by
its outcome, in order, with exact real timestamps from commit metadata (which also
eliminates the old problem of a local model guessing at "today's date").

**Squash-merge discipline is load-bearing here**, not just tidy — one commit per task on
`main` is what makes the git-log reconstruction clean. Temporary/WIP branches for
mid-task experimentation are fine; what matters is that only one commit per task ever
lands on `main` touching `project/task.md` and `project/report.md`.

---

## The Three Roles

### 1. Project Planner (harness, one-time per project)

**Invocation:** `project-planner {project-name}` (assumes cwd; project resolves
relative to it).

**Guard:** refuses to run if `project/design.md` already exists — this is a one-time
bootstrap, not a resumable session.

**Toolset:** exactly one tool — `bootstrap_project(design_md_content)`. Internally,
hardcoded, no model-controlled arguments beyond the content itself:
- `uv init`
- create `project/`
- write `design.md`
- `git init` if needed, one commit

Everything else in this session is pure chat, no tools. The planner's job:
- Take a rough idea and turn it into a scoped, understood project through discussion —
  clarifying questions, teaching foundational concepts, refining scope.
- Only call `bootstrap_project` once you signal you're ready to start building.
- Since this session's chat history does not persist anywhere after bootstrap, the
  planner should be pushed to make `design.md` genuinely complete — not a thin stub the
  architect has to awkwardly rediscover context for later.

**Does not create the first task.** That's the architect's responsibility, triggered by
the architect's own fresh-project detection on its first run (see below) — keeps the
planner single-responsibility (scoping + design only) rather than reaching into
task-creation logic that belongs to the other harness.

**`design.md` format:**

```markdown
# Project: [Name]

## Overview
[2-4 sentences: what this is, why it exists]

## Core Concepts
[High-level concepts the whole project rests on, taught during planning]

## Architecture
[Rough module/file map and responsibilities — high-level orientation only]

## Key Decisions
[Append-only log: date (from git) — decision — why]

## Known Trade-offs / Deferred Items
[Fed from Companion notes surfaced in report.md over time — things intentionally
 left suboptimal, and why]
```

---

### 2. Software Architect (harness, every session thereafter)

**Invocation:** `software-architect {project-name}` (assumes cwd).

**Guard:** refuses to run if `project/design.md` does **not** exist.

**On launch, the harness (not the model) determines state deterministically:**

1. Reads `design.md` and injects it as context automatically — no tool call needed.
2. Checks for `project/task.md` and `project/report.md`:
   - **Both absent** → fresh project, no tasks yet. Treat as "task 1 territory" — first
     order of business is teaching the first concept and calling `start_task`, with no
     history to check and no report to process.
   - **`task.md` exists, `report.md` still matches the harness's empty template** →
     current task is still in progress. Resume/continue discussion; do not treat this
     as a completed task ready for review.
   - **`task.md` exists, `report.md` has real content** → current task is ready for
     review.

This removes the state-detection logic that previously had to live inside the system
prompt (the old "State A/B/C" scaffolding) — it's now a deterministic filesystem check
the harness performs before the model ever sees a message.

**Toolset:**
- `read_file(path)` / `write_file(path, content)` — hard-scoped to `project/**` only,
  incapable of reaching `src/` or anywhere else. This boundary is enforced by the tool
  implementation itself, not by instruction.
- `start_task(task_name, task_md_content)` — deterministic: writes `task.md`, generates
  a fresh empty `report.md` from the harness's fixed template (no model involvement in
  the template itself — only `task.md`'s real content comes from the model), commits on
  `main` with a message convention like `Task N: name`, returns the branch name for you
  to check out.
- `get_recent_history(n=5)` — runs `git log -p` against `task.md` and `report.md`,
  interleaves them by commit order, returns the last *n* tasks' worth. Default lookup
  for "what's happened so far," capped so context doesn't balloon deep into a project.
- `search_task_history(query)` — greps commit messages (via the `Task N: name`
  convention) and/or file content for a match, returns the full paired history for that
  specific task. Answers things like "give me information on the rendering task"
  without you needing to know the task number.

**Responsibilities (same substance as v1, now without state-detection prompt logic):**
1. **Per-task teaching:** before writing a new `task.md`, teaches whatever concept that
   task introduces, grounded in the actual project, checking real comprehension before
   proceeding — not moving on just because an answer was attempted.
2. **Writing `task.md`** via `start_task` once teaching is done. One task at a time,
   never a backlog. Never contains implementation code, only plain-English spec.
3. **Task review:** once `report.md` is filled in (post-merge, on `main`), processes it
   in two parts —
   - *Your notes* (confusion, effort, friction — even without a hard blocker) → drives
     re-teaching
   - *Companion notes* (compliance results, deferred items) → each deferred item either
     becomes a `design.md` "Known Trade-offs" entry or spins into a future task,
     decided explicitly
   - A *Redesign flag* in the report triggers a scoped mini-replanning discussion,
     revising `design.md` and/or the in-progress `task.md`
4. **`design.md` maintenance:** amends Key Decisions / Known Trade-offs via
   `write_file` whenever something changes the project's shape.
5. **Periodic checkpoint:** every ~4 completed tasks (via `get_recent_history`), quizzes
   you cold — explain the last non-trivial concept back with no notes — before
   continuing.
6. **On-demand history lookups:** whenever you ask about a past task by name or topic,
   uses `search_task_history` rather than relying on chat memory.

**`task.md` format:**

```markdown
# Task N: [Name]

## Concept Recap
[1-3 sentences — what was just taught, so this file is self-contained]

## Goal
[What this task accomplishes, in plain terms]

## Inputs / Outputs
[Concrete: what state/data this task's code receives and produces]

## Constraints
[Anything limiting the approach]

## Acceptance Criteria
[Numbered. Tag each [TESTABLE] or [QUALITATIVE].
 TESTABLE = expressible as a pass/fail assertion.
 QUALITATIVE = requires judgment.
 Aim for as many TESTABLE criteria as the task honestly supports.]

## Explicitly Out of Scope
[What this task deliberately does NOT cover]
```

**`report.md` template (harness-generated, empty, for you to fill in):**

```markdown
## My notes
[What you built, what you were confused about, where effort actually went —
 including slow friction that wasn't a hard blocker]

## Companion notes
[Compliance results from the Companion's review, plus any deferred/optimization
 items it flagged that you chose not to act on now]

## Redesign flag
[Only fill in if this task revealed a need to revisit design.md or the current
 task.md — otherwise leave blank/omit]
```

---

### 3. Companion (in-editor, unchanged from v1)

**Where it lives:** Continue.dev / Aider-style tool in your editor, pointed at the
local model server, with a custom system prompt.

**Context:** full repo access — source code, `task.md`, `design.md` for the current
task. Not part of the harness architecture above; it has no reason to touch `project/`
programmatically since you transcribe its findings into `report.md` yourself.

**How it's used** — one ongoing chat, different kinds of asks, no rigid mode-switching:
- **General collaboration:** "what do you think of this function," "is there a stdlib
  way to do this," normal assistant use during drafting.
- **Comment-only pairing while drafting:** critiques and questions, doesn't rewrite your
  code for you, except by your own judgment call (stuck for a while, or unrelated
  boilerplate).
- **On-demand compliance check:** ask directly, any time — looks at staged changes or
  `git diff main...task-branch` and evaluates against `task.md`'s acceptance criteria.
- **Optional TDD support:** for `[TESTABLE]` criteria, ask it to generate tests upfront
  before drafting — gives you a concrete target and doubles as a sanity check on the
  spec (if it can't write a sensible test from a criterion, that criterion was
  underspecified). Skip for `[QUALITATIVE]` criteria.

**Authority: advisory only, never blocking.** A flagged optimization or deviation
doesn't prevent a merge — you decide. Anything you choose to defer gets written into
`report.md`'s Companion notes so the Architect can plan around it later.

---

## The Task Loop

1. **First run only:** `software-architect` detects no `task.md`/`report.md` exist,
   treats this as task 1, teaches the first concept, and calls `start_task`.
   **Every run after:** harness detects current state (in progress / ready for review)
   from the filesystem, and the architect proceeds accordingly.
2. Architect teaches the task's concept (if new) → calls `start_task` → gives you the
   branch name.
3. `git checkout -b task-N-name`.
4. Decide test coverage for `[TESTABLE]` criteria (optionally ask Companion to generate
   tests upfront from `task.md`).
5. Draft, running tests as you go, collaborating with the Companion freely.
6. On-demand compliance check(s) with the Companion whenever useful — not a gate.
7. Fill in `report.md` — your notes and Companion notes in their own sections.
8. Commit, **squash-merge** to `main` (one commit, discipline matters here).
9. Tell the architect the task is done. It reads the now-current `report.md` off
   `main` (harness injects it, same as `design.md`), processes both note sections,
   amends `design.md` if warranted, then teaches the next concept and starts the next
   task.

**Every ~4 tasks:** cold quiz checkpoint before the next task starts.

**Mid-task redesign:** flag it in that task's `report.md` under "Redesign flag" —
the architect treats it as a scoped mini-replanning discussion when it next reads
that report.

---

## Open Questions / Things to Decide

- Exact commit message convention for `start_task` (`Task N: name` assumed above) —
  needs to be consistent since `search_task_history` greps against it.
- Threshold for when the Companion may rewrite instead of just comment.
- Model choice per harness: a general reasoning model (Qwen3 14B, Phi-4 14B, Gemma 3
  12B at the 12GB VRAM tier) suits the Planner and Architect's teaching/design work; a
  code-specialized model (Qwen2.5-Coder, DeepSeek-Coder-V2) suits the Companion.
- Harness implementation: single script with `planner`/`architect` subcommands sharing
  tool-loop infrastructure, versus two separate scripts — to be decided before
  implementation begins.
