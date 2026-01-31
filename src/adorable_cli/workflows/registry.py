from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

import yaml

from adorable_cli import config as cfg


class UnknownWorkflowError(ValueError):
    """Raised when a workflow id is not found."""


@dataclass
class WorkflowResult:
    output: str


@dataclass
class Workflow:
    workflow_id: str
    description: str
    requires_component: bool
    runner: Callable[..., Awaitable[WorkflowResult]]

    async def run(self, **kwargs: Any) -> WorkflowResult:
        return await self.runner(**kwargs)


def _summarize_diff(diff_text: str) -> tuple[int, int, int]:
    files: set[str] = set()
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            files.add(line)
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return len(files), added, removed


async def _run_research(**_: Any) -> WorkflowResult:
    output = "\n".join(
        [
            "# Research Workflow",
            "",
            "## Search",
            "Summary of sources and queries would go here.",
            "",
            "## Analysis",
            "Key themes and synthesis would go here.",
            "",
            "## Answer",
            "Final answer would go here.",
        ]
    )
    return WorkflowResult(output=output)


async def _run_code_review(
    *,
    input_text: str = "",
    diff_file: Path | None = None,
    **_: Any,
) -> WorkflowResult:
    diff_text = input_text
    if diff_file is not None:
        try:
            diff_text = diff_file.read_text(encoding="utf-8")
        except Exception:
            diff_text = ""

    files_changed, lines_added, lines_removed = _summarize_diff(diff_text)
    output = "\n".join(
        [
            "# Code Review Report",
            f"Files changed: {files_changed}",
            f"Lines added: {lines_added}",
            f"Lines removed: {lines_removed}",
        ]
    )
    return WorkflowResult(output=output)


def _builtin_workflows() -> list[Workflow]:
    return [
        Workflow(
            workflow_id="research",
            description="Research a question and provide a structured answer.",
            requires_component=False,
            runner=_run_research,
        ),
        Workflow(
            workflow_id="code-review",
            description="Review a diff and summarize changes.",
            requires_component=False,
            runner=_run_code_review,
        ),
    ]


def _load_custom_workflows() -> Iterable[Workflow]:
    workflows_dir = cfg.WORKFLOWS_DIR
    if not workflows_dir.exists():
        return []

    workflows: list[Workflow] = []
    for path in sorted(workflows_dir.iterdir()):
        if path.suffix.lower() not in {".yaml", ".yml"}:
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        workflow_id = str(data.get("name") or path.stem).strip()
        if not workflow_id:
            continue
        description = str(data.get("description") or "Custom workflow").strip()

        async def _run_custom(
            *,
            offline: bool = False,
            workflow_key: str = workflow_id,
            **__: Any,
        ) -> WorkflowResult:
            if offline:
                return WorkflowResult(
                    output=f"Offline mode not supported for custom workflow '{workflow_key}' yet"
                )
            return WorkflowResult(output=f"Custom workflow '{workflow_key}' is not implemented yet.")

        workflows.append(
            Workflow(
                workflow_id=workflow_id,
                description=description,
                requires_component=False,
                runner=_run_custom,
            )
        )
    return workflows


def list_workflows() -> list[Workflow]:
    workflows = _builtin_workflows()
    workflows.extend(list(_load_custom_workflows()))
    return workflows


def get_workflow(workflow_id: str) -> Workflow:
    for wf in list_workflows():
        if wf.workflow_id == workflow_id:
            return wf
    raise UnknownWorkflowError(f"Unknown workflow: {workflow_id}")
