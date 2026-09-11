#!/usr/bin/env python3
"""
software-architect {project-name}

Recurring per-task teaching, spec-writing, and review. Assumes cwd: the
project lives at ./{project-name}, already bootstrapped by project-planner.

State (fresh / in_progress / ready_for_review) is detected here, in code,
before the model ever sees a message — not inferred by the model from chat.
"""

import sys
from pathlib import Path

from harness import git_tools, task_tools
from harness.chat_loop import ToolSpec, run_chat_loop
from harness.config import Config
from harness.fs_tools import PathEscapeError, ScopedFS

PROMPT_PATH = Path(__file__).parent / "prompts" / "architect_system_prompt.md"


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: software-architect {project-name}", file=sys.stderr)
        sys.exit(1)

    project_name = sys.argv[1]
    project_dir = Path.cwd() / project_name
    design_path = project_dir / "project" / "design.md"

    if not design_path.exists():
        print(
            f"Error: {design_path} does not exist. This project hasn't been "
            f"bootstrapped yet — run `project-planner {project_name}` first."
        )
        sys.exit(1)

    config = Config.load("architect")
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    scoped_fs = ScopedFS(project_dir / "project")

    # --- Deterministic state detection, done here, not by the model ---
    state = task_tools.detect_state(project_dir)
    design_content = design_path.read_text(encoding="utf-8")

    context_messages = [
        {"role": "system", "content": f"Current design.md content:\n\n{design_content}"}
    ]

    if state == "fresh":
        opening_line = (
            "Software Architect — fresh project, no tasks yet. "
            "I'll pick up from design.md and get task 1 started."
        )
    else:
        task_content = scoped_fs.read_file("task.md")
        report_content = scoped_fs.read_file("report.md")
        context_messages.append({
            "role": "system",
            "content": (
                f"Current state: {state}\n\n"
                f"Current task.md content:\n\n{task_content}\n\n"
                f"Current report.md content:\n\n{report_content}"
            ),
        })
        if state == "in_progress":
            opening_line = "Software Architect — current task is still in progress. Welcome back."
        else:
            opening_line = "Software Architect — report.md looks filled in. Ready to review when you are."

    # --- Tool bindings ---

    def _read_file(path: str) -> dict:
        try:
            return {"status": "ok", "content": scoped_fs.read_file(path)}
        except (FileNotFoundError, PathEscapeError) as e:
            return {"status": "error", "message": str(e)}

    def _write_file(path: str, content: str) -> dict:
        try:
            scoped_fs.write_file(path, content)
            return {"status": "ok"}
        except PathEscapeError as e:
            return {"status": "error", "message": str(e)}

    def _start_task(task_name: str, task_md_content: str) -> dict:
        result = task_tools.start_task(project_dir, task_name, task_md_content)
        print(f"\n[{result['message']}]\n")
        return result

    def _get_recent_history(n: int = 5) -> dict:
        return {"status": "ok", "history": git_tools.get_history(project_dir, n=n)}

    def _search_task_history(query: str) -> dict:
        return {"status": "ok", "history": git_tools.search_history(project_dir, query)}

    tools = {
        "read_file": ToolSpec(
            name="read_file",
            description="Read a file's content, scoped to the project/ directory only.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            fn=_read_file,
        ),
        "write_file": ToolSpec(
            name="write_file",
            description=(
                "Write a file's content, scoped to the project/ directory only. "
                "Use for design.md updates (Key Decisions, Known Trade-offs, redesigns)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            fn=_write_file,
        ),
        "start_task": ToolSpec(
            name="start_task",
            description=(
                "Writes task.md, resets report.md to a fresh template, commits both "
                "on main, and returns the branch name to check out. Call once teaching "
                "for this task is complete and task.md content is ready."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_name": {"type": "string", "description": "Short task name, e.g. 'jump-physics'."},
                    "task_md_content": {"type": "string", "description": "Complete task.md content."},
                },
                "required": ["task_name", "task_md_content"],
            },
            fn=_start_task,
        ),
        "get_recent_history": ToolSpec(
            name="get_recent_history",
            description="Returns the last n tasks' worth of task.md/report.md git history, chronological.",
            parameters={
                "type": "object",
                "properties": {"n": {"type": "integer", "description": "Number of recent tasks. Default 5."}},
                "required": [],
            },
            fn=_get_recent_history,
        ),
        "search_task_history": ToolSpec(
            name="search_task_history",
            description="Finds a past task by keyword/topic (matches commit messages and file content).",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            fn=_search_task_history,
        ),
    }

    run_chat_loop(
        config=config,
        system_prompt=system_prompt,
        tools=tools,
        context_messages=context_messages,
        opening_line=opening_line,
    )


if __name__ == "__main__":
    main()
