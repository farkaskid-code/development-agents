"""
Project bootstrap — the planner's single tool.

Deliberately not exposed as a generic "run shell command" capability. The
model supplies only design.md's content; every mechanical step here is fixed
and cannot be parameterized by the model beyond that one string.
"""

import subprocess
from pathlib import Path

from . import git_tools


def bootstrap_project(project_dir: Path, design_md_content: str) -> dict:
    project_dir.mkdir(parents=True, exist_ok=True)

    if not (project_dir / "pyproject.toml").exists():
        result = subprocess.run(
            ["uv", "init", "."], cwd=project_dir, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"uv init failed: {result.stderr}")

    project_subdir = project_dir / "project"
    project_subdir.mkdir(exist_ok=True)
    (project_subdir / "design.md").write_text(design_md_content, encoding="utf-8")

    git_tools.init_repo(project_dir)
    git_tools.commit_all(project_dir, "Bootstrap: initial design.md")

    return {
        "status": "ok",
        "project_path": str(project_dir),
        "message": (
            f"Project bootstrapped at {project_dir}. "
            f"Run `software-architect` for this project next to start task 1."
        ),
    }
