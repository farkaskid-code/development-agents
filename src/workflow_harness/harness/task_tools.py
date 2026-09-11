"""
Task lifecycle mechanics for the Architect harness.

State detection (fresh / in_progress / ready_for_review) is deterministic —
a filesystem check the harness performs before the model ever sees a
message — rather than something the model has to infer from conversation.
"""

import re
from pathlib import Path

from . import git_tools

REPORT_TEMPLATE = """## My notes
[What you built, what you were confused about, where effort actually went —
including slow friction that wasn't a hard blocker]

## Companion notes
[Compliance results from the Companion's review, plus any deferred/optimization
items it flagged that you chose not to act on now]

## Redesign flag
[Only fill in if this task revealed a need to revisit design.md or the current
task.md — otherwise leave blank/omit]
"""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "task"


def detect_state(project_dir: Path) -> str:
    task_path = project_dir / "project" / "task.md"
    report_path = project_dir / "project" / "report.md"

    if not task_path.exists() and not report_path.exists():
        return "fresh"

    if report_path.exists() and report_path.read_text(encoding="utf-8").strip() == REPORT_TEMPLATE.strip():
        return "in_progress"

    return "ready_for_review"


def start_task(project_dir: Path, task_name: str, task_md_content: str) -> dict:
    project_subdir = project_dir / "project"
    project_subdir.mkdir(exist_ok=True)

    task_number = git_tools.get_next_task_number(project_dir)

    (project_subdir / "task.md").write_text(task_md_content, encoding="utf-8")
    (project_subdir / "report.md").write_text(REPORT_TEMPLATE, encoding="utf-8")

    commit_message = f"Task {task_number}: {task_name}"
    git_tools.commit_all(project_dir, commit_message)

    branch_name = f"task-{task_number}-{slugify(task_name)}"

    return {
        "status": "ok",
        "task_number": task_number,
        "suggested_branch": branch_name,
        "message": (
            f"task.md written and committed on main as '{commit_message}'. "
            f"Create and check out branch '{branch_name}' to start work."
        ),
    }
