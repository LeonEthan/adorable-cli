from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from adorable_cli import config as cfg
from adorable_cli.teams.builder import create_team
from adorable_cli.workflows.types import WorkflowResult, WorkflowSpec
from adorable_cli.workflows.utils import run_component


@dataclass
class WorkflowStep:
    id: str
    name: str
    agent: str | None
    instruction: str


@dataclass
class YamlWorkflow:
    name: str
    description: str
    steps: list[WorkflowStep]


def _substitute(text: str, context: dict[str, str]) -> str:
    """
    Simple template substitution for {{ variable }}.
    """
    def replace(match):
        key = match.group(1).strip()
        return context.get(key, match.group(0))

    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", replace, text)


async def _run_yaml_workflow(
    workflow: YamlWorkflow,
    input_text: str,
    component: Any | None = None,
    offline: bool = False,
    session_id: str | None = None,
    user_id: str | None = None,
) -> WorkflowResult:
    if offline:
        return WorkflowResult(
            workflow_id=workflow.name,
            output=f"Offline mode not supported for custom workflow '{workflow.name}' yet.",
        )

    context = {"input": input_text}
    output_parts = []
    
    # Header
    output_parts.append(f"# Workflow: {workflow.description or workflow.name}\n")

    for step in workflow.steps:
        # Resolve component for this step
        step_component = component
        if step.agent:
            try:
                # Create a fresh team/agent for the step
                # Note: We rely on default params for db/managers for now.
                # If persistent memory is needed, we might need to inject dependencies.
                step_component = create_team(step.agent)
            except Exception as e:
                error_msg = f"Error creating agent '{step.agent}' for step '{step.id}': {e}"
                output_parts.append(f"## {step.name}\n[Error] {error_msg}")
                break
        
        if not step_component:
            output_parts.append(f"## {step.name}\n[Skipped] No agent available.")
            continue

        instruction = _substitute(step.instruction, context)
        
        try:
            step_output = await run_component(
                step_component, 
                instruction, 
                session_id=session_id, 
                user_id=user_id
            )
        except Exception as e:
            step_output = f"[Error executing step] {e}"

        context[step.id] = step_output
        context[f"{step.id}.output"] = step_output
        
        output_parts.append(f"## {step.name}\n{step_output}\n")

    return WorkflowResult(workflow_id=workflow.name, output="\n".join(output_parts))


def _parse_steps(raw_steps: list[Any]) -> list[WorkflowStep]:
    steps = []
    for idx, item in enumerate(raw_steps):
        if not isinstance(item, dict):
            continue
        
        step_id = item.get("id") or f"step_{idx+1}"
        name = item.get("name") or step_id.replace("_", " ").title()
        agent = item.get("agent")
        instruction = item.get("instruction", "")
        
        steps.append(WorkflowStep(id=step_id, name=name, agent=agent, instruction=instruction))
    return steps


def _load_yaml_workflow(path: Path) -> WorkflowSpec | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
            
        name = data.get("name")
        if not name:
            return None
            
        description = data.get("description", "")
        raw_steps = data.get("steps", [])
        if not raw_steps:
            return None
            
        workflow = YamlWorkflow(
            name=name,
            description=description,
            steps=_parse_steps(raw_steps),
        )

        async def run_wrapper(
            *,
            input_text: str,
            component: Any | None = None,
            offline: bool = False,
            session_id: str | None = None,
            user_id: str | None = None,
            **kwargs,
        ) -> WorkflowResult:
            return await _run_yaml_workflow(
                workflow,
                input_text,
                component=component,
                offline=offline,
                session_id=session_id,
                user_id=user_id,
            )

        return WorkflowSpec(
            workflow_id=name,
            description=description,
            run=run_wrapper,
        )

    except Exception:
        # Log error?
        return None


def load_user_workflows(workflows_dir: Path | None = None) -> list[WorkflowSpec]:
    workflows_dir = workflows_dir or cfg.WORKFLOWS_DIR
    if not workflows_dir.exists():
        return []

    specs = []
    for p in workflows_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".yaml", ".yml"):
            continue
        
        spec = _load_yaml_workflow(p)
        if spec:
            specs.append(spec)
            
    return specs
