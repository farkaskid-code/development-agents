#!/usr/bin/env python3
"""
project-planner {project-name}

One-time project scoping. Discusses the idea, teaches foundational concepts,
and — once you're ready — bootstraps the project directory via its one tool.
Assumes cwd: the project is created at ./{project-name}.
"""

import sys
from pathlib import Path

from harness.bootstrap import bootstrap_project
from harness.chat_loop import ToolSpec, run_chat_loop, console
from harness.config import Config

PROMPT_PATH = Path(__file__).parent / "prompts" / "planner_system_prompt.md"


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: project-planner {project-name}", file=sys.stderr)
        sys.exit(1)

    project_name = sys.argv[1]
    project_dir = Path.cwd() / project_name
    design_path = project_dir / "project" / "design.md"

    if design_path.exists():
        print(
            f"Error: {design_path} already exists — this project is already "
            f"bootstrapped. Use `software-architect {project_name}` instead."
        )
        sys.exit(1)

    config = Config.load("planner")
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def _bootstrap(design_md_content: str) -> dict:
        result = bootstrap_project(project_dir, design_md_content)
        console.print(f"\n{result['message']}\n", style="bold green", markup=False)
        return result

    tools = {
        "bootstrap_project": ToolSpec(
            name="bootstrap_project",
            description=(
                "Sets up the project directory, initializes it with uv and git, "
                "and writes design.md. Call this only once the person has clearly "
                "signaled they're ready to start building. Ends this session."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "design_md_content": {
                        "type": "string",
                        "description": "The complete content for design.md, following the required format.",
                    }
                },
                "required": ["design_md_content"],
            },
            fn=_bootstrap,
            ends_session=True,
        )
    }

    run_chat_loop(
        config=config,
        system_prompt=system_prompt,
        tools=tools,
        opening_line=f"Project Planner — new project '{project_name}'. What are you thinking of building?",
        assistant_label="Planner",
    )


if __name__ == "__main__":
    main()
