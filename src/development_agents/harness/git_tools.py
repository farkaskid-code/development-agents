"""
Git operations backing the workflow's "history is git history" design.

The devlog isn't a file — it's `git log -p` against task.md and report.md,
interleaved by commit order. This module is what makes that real.
"""

import re
import subprocess
from pathlib import Path

TASK_COMMIT_RE = re.compile(r"^Task (\d+): (.+)$")
TRACKED_PATHS = ["project/task.md", "project/report.md"]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def init_repo(cwd: Path) -> None:
    if not (cwd / ".git").exists():
        result = _run(["init"], cwd=cwd)
        if result.returncode != 0:
            raise RuntimeError(f"git init failed: {result.stderr}")


def setup_dev_branch(cwd: Path) -> None:
    rename_main_branch = _run(["branch", "-m", "main"], cwd=cwd)
    if rename_main_branch.returncode != 0:
        raise RuntimeError(
            f"failed to rename main branch to 'main': {rename_main_branch.stderr}"
        )

    create_dev_branch = _run(["checkout", "-b", "dev"], cwd=cwd)
    if create_dev_branch.returncode != 0:
        raise RuntimeError(f"failed to create dev branch: {create_dev_branch.stderr}")


def commit_all(cwd: Path, message: str) -> None:
    add = _run(["add", "-A"], cwd=cwd)
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr}")
    commit = _run(["commit", "-m", message], cwd=cwd)
    if commit.returncode != 0:
        # Nothing to commit is a common, harmless case (e.g. re-running with
        # identical content) — surface it plainly rather than raising.
        if "nothing to commit" in commit.stdout.lower():
            return
        raise RuntimeError(f"git commit failed: {commit.stderr or commit.stdout}")


def get_next_task_number(cwd: Path) -> int:
    """
    Infers the next task number from prior 'Task N: name' commit messages
    touching task.md on the current branch. Relies on squash-merge discipline
    (one such commit per task on main) — see workflow docs.
    """
    result = _run(
        ["log", "--pretty=%s", "--", "project/task.md"],
        cwd=cwd,
    )
    if result.returncode != 0:
        return 1
    numbers = []
    for line in result.stdout.splitlines():
        m = TASK_COMMIT_RE.match(line.strip())
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers, default=0) + 1


def get_history(cwd: Path, n: int | None = None) -> str:
    """
    Returns the interleaved commit history (with patches) for task.md and
    report.md, in chronological (oldest-first) commit order. This is the
    reconstructed devlog. If n is given, trims to the last n commits touching
    either file (a "commit" here may include both files if they changed
    together, which is the normal case for a squash-merged task).
    """
    args = ["log", "-p", "--reverse", "--", *TRACKED_PATHS]
    result = _run(args, cwd=cwd)
    if result.returncode != 0:
        return ""
    log_text = result.stdout
    if n is None:
        return log_text

    # Trim to the last n commit blocks, keeping reverse (chronological) order.
    blocks = re.split(r"(?=^commit [0-9a-f]{40}$)", log_text, flags=re.MULTILINE)
    blocks = [b for b in blocks if b.strip()]
    return "".join(blocks[-n:])


def search_history(cwd: Path, query: str) -> str:
    """
    Finds commits touching task.md/report.md whose message OR content
    matches `query` (case-insensitive), returns their full patches.
    Covers both "the rendering task" (likely a message match) and queries
    aimed at what was actually built (a content match).
    """
    by_message = _run(
        ["log", "-p", "-i", f"--grep={query}", "--", *TRACKED_PATHS],
        cwd=cwd,
    )
    by_content = _run(
        ["log", "-p", "-i", f"-S{query}", "--", *TRACKED_PATHS],
        cwd=cwd,
    )
    parts = []
    if by_message.returncode == 0 and by_message.stdout.strip():
        parts.append("=== Matches by commit message ===\n" + by_message.stdout)
    if by_content.returncode == 0 and by_content.stdout.strip():
        parts.append("=== Matches by file content change ===\n" + by_content.stdout)
    return "\n\n".join(parts) if parts else f"No history found matching '{query}'."
