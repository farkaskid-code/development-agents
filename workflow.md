# Development Workflow

A learning-first workflow for building personal software projects with a local LLM,
split across three roles: a **Project Planner** (one-time scoping), a **Software
Architect** (recurring teaching + task design), and a **Companion** (in-editor pairing
and review). This document describes the workflow itself — how the roles interact and
why they're split the way they are. For how to install and run the tooling that
implements the Planner and Architect, see the repository's `README.md`.

## Why split it up this way

A single AI assistant handling both "help me design this" and "write the code" tends to
collapse into just generating code the moment something unfamiliar comes up — which
defeats the point if the goal is to actually learn what you're building, not just end up
with something that runs. This workflow deliberately separates:

- **Design and teaching** (the Planner and the Architect) from **writing code** (you,
  with the Companion assisting) — the Planner and Architect never write implementation
  code, full stop.
- **One-time scoping** (the Planner) from **recurring, per-task work** (the Architect) —
  these are genuinely different jobs with different lifespans, so they're different
  tools with different context windows, rather than one persona trying to hold both.

State lives in files and in git history, not in conversation memory. Chat is scratch
space — anything that should persist gets written down immediately, by the tooling
itself wherever possible, rather than relying on a person to remember to save it.

---

## Two kinds of "project" — don't conflate these

This workflow is implemented by a small tool, `development-agents` (this repository).
That tool is used to build **other** projects — e.g. a terminal clone of a game, a CLI
utility, whatever the person building it wants to make. Two different directory
structures are in play, and it matters to keep them straight:

- **This repository** (`development-agents`) — a Python package containing the Planner
  and Architect CLIs.
- **A project you build with it** (e.g. `dino-game/`) — created by the Planner, lives
  wherever you choose to run these tools from, and has its own small directory
  structure described below. It has nothing to do with this repo's own layout.

---

## Structure of a project built with this tool

```
dino-game/                 # a project created via `project-planner dino-game`
  project/
    design.md               # durable project state — Planner writes once, Architect amends
    task.md                  # current task's spec only — overwritten each task cycle
    report.md                 # current task's outcome — template by the tool, content by you
  src/                        # your actual code — the Architect never reads this directory
```

Only three files under `project/`, always current-state-only for `task.md`/`report.md`.
There is no separate devlog file — **git history against these two files is the
devlog.** Because each task branch is squash-merged into a single commit on `main`,
`git log -p` against `task.md` and `report.md`, interleaved by commit order,
reconstructs the full development history: each task's spec followed by its outcome, in
order, with exact real timestamps taken from commit metadata.

**Squash-merge discipline matters here, not just for tidiness** — one commit per task on
`main` is what keeps the git-log reconstruction clean. Temporary/WIP branches for
mid-task experimentation are fine; what matters is that only one commit per task ever
lands on `main` touching `project/task.md` and `project/report.md`.

---

## The Three Roles

### 1. Project Planner (one-time, per project)

Run once, at the very start of a new project. Its only job is to turn a rough idea into
a scoped, understood project through conversation — clarifying questions, teaching
whatever foundational concepts the project rests on, refining scope — and then to
produce `design.md`.

It has exactly one tool available to it: an action that sets up the new project's
directory (initializing it, creating `project/`, and writing `design.md`). It cannot run
arbitrary commands — that one action is fixed and only ever takes the finished
`design.md` content as input. This session's conversation does not persist anywhere
after that point, so `design.md` needs to be genuinely complete when it's written — not
a thin stub that leaves the next role to rediscover context that only ever existed in
this chat.

The Planner does **not** create the first task — that is deliberately left to the
Architect (see below), so the Planner's job stays limited to scoping and design.

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
[Starts empty — filled in later, during actual development]
```

### 2. Software Architect (recurring, every session after that)

Run every time you sit down to work on the project after it's been scoped. On startup,
it deterministically checks the state of `project/task.md` and `project/report.md` on
disk — this state detection is done in code, not left to the model to infer from
conversation:

- **Neither file exists** → fresh project, no tasks yet. Treated as "task 1" — the
  Architect teaches the first concept and creates the first task.
- **`task.md` exists, `report.md` is still an empty template** → the current task is in
  progress. The Architect continues teaching/discussing, but does not start reviewing.
- **`task.md` exists, `report.md` has real content** → the current task is ready for
  review.

Like the Planner, the Architect never writes implementation code and never sees the
actual source code, diffs, or the editor. Its file access is scoped to the `project/`
directory only — it cannot read or write anything under `src/`, and that boundary is
enforced by the tool itself rather than by instruction alone.

**Per task, its responsibilities are:**

1. **Teach** whatever concept the upcoming task introduces, grounded in the actual
   project, checking real comprehension before moving on — not just accepting a
   first-attempt answer.
2. **Write `task.md`** for exactly one task at a time — never a backlog — and hand back
   a branch name to check out.
3. **Review `report.md`** once it's filled in, treating two sections differently:
   - *Your own notes* (confusion, effort, friction) → drives what gets re-taught
   - *Companion notes* (compliance results, deferred items from your editor assistant)
     → each deferred item either becomes a note in `design.md`'s trade-offs section, or
     spins into its own future task
   - A *Redesign flag*, if present, triggers a scoped re-discussion of `design.md`
     and/or the current task, rather than silently proceeding
4. **Maintain `design.md`** — appending Key Decisions and Known Trade-offs whenever
   something changes the shape of the project.
5. **Check in periodically** (roughly every 4 completed tasks) by asking you to explain
   the most recent non-trivial concept back from memory, before continuing — a cheap
   way to catch understanding gaps before they compound.
6. **Look up history on request** — by task number, or by topic/keyword if you don't
   remember which task something was.

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
 As many TESTABLE criteria as the task honestly supports — a criterion that can't
 be tagged either way is underspecified and should be sharpened before finishing.]

## Explicitly Out of Scope
[What this task deliberately does NOT cover]
```

**`report.md` template** (generated automatically, empty, for you to fill in):

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

### 3. Companion (in-editor, not part of this repo)

A separate, ordinary code-assistant setup in your editor (e.g. Continue.dev, Aider, or
similar, pointed at the same or a different local model), with a custom system prompt.
It's not implemented by this repository — it just needs full access to the actual
source code, `task.md`, and `design.md` for whichever task is current.

**How it's used** — one ongoing chat, different kinds of requests, no rigid
mode-switching:

- **General collaboration** — "what do you think of this function," "is there a stdlib
  way to do this" — ordinary assistant use while drafting.
- **Comment-only pairing while drafting** — it critiques and asks questions rather than
  rewriting your code outright, except by your own judgment call (you've been stuck a
  while, or it's unrelated boilerplate).
- **On-demand compliance check** — ask any time, and it evaluates your current diff
  against `task.md`'s acceptance criteria.
- **Optional test generation** — for `[TESTABLE]` criteria, you can ask it to write
  tests upfront before drafting, which gives you a concrete target and doubles as a
  sanity check on the spec itself. Skip this for `[QUALITATIVE]` criteria, where a test
  wouldn't capture the actual judgment call being asked for.

**Its verdict is advisory, never blocking.** A flagged optimization or deviation
doesn't prevent a merge — you decide. Anything you choose to defer gets written into
`report.md`'s Companion notes so the Architect can plan around it later.

---

## The Task Loop, End to End

1. **First run:** the Architect detects no `task.md`/`report.md` exist, treats it as
   task 1, teaches the relevant concept, and creates the task. **Every run after:** it
   detects current state from the filesystem and proceeds accordingly.
2. Architect teaches the task's concept (if new) → creates the task → gives you the
   branch name.
3. Check out that branch.
4. Decide test coverage for `[TESTABLE]` criteria (optionally ask the Companion to
   generate tests upfront from `task.md`).
5. Draft the code, running tests as you go, collaborating with the Companion freely.
6. Ask the Companion for an on-demand compliance check whenever useful — it's
   informative, not a gate.
7. Fill in `report.md` — your notes and the Companion's notes in their own sections.
8. Commit, **squash-merge** to `main`.
9. Tell the Architect the task is done. It reads the now-current `report.md`, processes
   both note sections, amends `design.md` if warranted, then teaches the next concept
   and starts the next task.

**Every ~4 tasks:** a cold checkpoint before the next task starts — explain the last
concept back with no notes.

**Mid-task redesign:** flag it in that task's `report.md` under "Redesign flag" — the
Architect treats it as a scoped re-discussion the next time it reads that report.

---

## Design Notes Worth Knowing

- **No date-guessing.** Every timestamp in the reconstructed history comes from real
  git commit metadata, not a model's (often stale) sense of "today."
- **The Architect's inability to touch `src/` is enforced in code**, not by asking it
  nicely in a prompt — a boundary a local model could otherwise drift from over a long
  session.
- **The Planner cannot run arbitrary shell commands.** Its one tool performs a fixed
  sequence with no model-controlled arguments beyond the content of `design.md` itself.
