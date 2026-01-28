from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from agno.models.openai import OpenAILike
from agno.team import Team

from adorable_cli.agent.main_agent import create_adorable_agent
from adorable_cli.agent.policy import ToolPolicy
from adorable_cli.agent.prompts import AGENT_INSTRUCTIONS, AGENT_ROLE
from adorable_cli.settings import settings


class TeamConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AgentPreset:
    preset_id: str
    name: str
    role: str
    instructions: list[str]
    tool_policy: ToolPolicy


def _mk_instructions(*extra: str) -> list[str]:
    instructions = list(AGENT_INSTRUCTIONS)
    instructions.extend([e for e in extra if e and e.strip()])
    return instructions


_PRESETS: dict[str, AgentPreset] = {
    "planner": AgentPreset(
        preset_id="planner",
        name="Planner",
        role=f"{AGENT_ROLE}. Primary focus: planning and decomposition.",
        instructions=_mk_instructions(
            "You are the Planner. Break the task into steps, identify risks, and propose a plan. "
            "Prefer analysis and clear next actions over implementation details."
        ),
        tool_policy=ToolPolicy.from_mode("confirm"),
    ),
    "coder": AgentPreset(
        preset_id="coder",
        name="Coder",
        role=f"{AGENT_ROLE}. Primary focus: implementation.",
        instructions=_mk_instructions(
            "You are the Coder. Implement the requested changes with minimal diffs. "
            "Prefer using existing patterns and keep codebase conventions."
        ),
        tool_policy=ToolPolicy(),
    ),
    "tester": AgentPreset(
        preset_id="tester",
        name="Tester",
        role=f"{AGENT_ROLE}. Primary focus: tests and validation.",
        instructions=_mk_instructions(
            "You are the Tester. Add or update unit tests for changes. "
            "Prefer deterministic tests and validate expected behavior."
        ),
        tool_policy=ToolPolicy(),
    ),
    "searcher": AgentPreset(
        preset_id="searcher",
        name="Searcher",
        role=f"{AGENT_ROLE}. Primary focus: gather information and evidence.",
        instructions=_mk_instructions(
            "You are the Searcher. Find relevant facts in code, docs, and reliable sources. "
            "Prefer precise citations and avoid speculation."
        ),
        tool_policy=ToolPolicy.from_mode("confirm"),
    ),
    "analyst": AgentPreset(
        preset_id="analyst",
        name="Analyst",
        role=f"{AGENT_ROLE}. Primary focus: analysis and synthesis.",
        instructions=_mk_instructions(
            "You are the Analyst. Synthesize findings into a clear answer or recommendation. "
            "Highlight tradeoffs and constraints."
        ),
        tool_policy=ToolPolicy.from_mode("confirm"),
    ),
    "writer": AgentPreset(
        preset_id="writer",
        name="Writer",
        role=f"{AGENT_ROLE}. Primary focus: produce the final write-up.",
        instructions=_mk_instructions(
            "You are the Writer. Produce concise, well-structured output. "
            "Make results easy to scan and actionable."
        ),
        tool_policy=ToolPolicy.from_mode("confirm"),
    ),
}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise TeamConfigError(f"Failed to parse YAML: {path}") from e
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TeamConfigError(f"Invalid team YAML (expected mapping): {path}")
    return raw


def _parse_policy(obj: Any) -> ToolPolicy | None:
    if obj is None:
        return None
    if isinstance(obj, str):
        return ToolPolicy.from_mode(obj)
    if isinstance(obj, dict):
        mode = obj.get("mode")
        base = ToolPolicy.from_mode(mode)
        allow_shell = obj.get("allow_shell")
        allow_file_write = obj.get("allow_file_write")
        allow_python = obj.get("allow_python")
        confirm_file_write = obj.get("confirm_file_write")
        return ToolPolicy(
            allow_shell=base.allow_shell if allow_shell is None else bool(allow_shell),
            allow_file_write=base.allow_file_write if allow_file_write is None else bool(allow_file_write),
            allow_python=base.allow_python if allow_python is None else bool(allow_python),
            confirm_file_write=base.confirm_file_write
            if confirm_file_write is None
            else bool(confirm_file_write),
        )
    raise TeamConfigError("Invalid permissions policy (expected string or mapping)")


def _parse_agents(obj: Any) -> list[dict[str, Any]]:
    if not isinstance(obj, list) or not obj:
        raise TeamConfigError("Team YAML must include non-empty 'agents' list")
    normalized: list[dict[str, Any]] = []
    for item in obj:
        if isinstance(item, str):
            normalized.append({"preset": item})
        elif isinstance(item, dict):
            normalized.append(dict(item))
        else:
            raise TeamConfigError("Each agent must be a string preset id or mapping")
    return normalized


def _get_preset(preset_id: str) -> AgentPreset:
    pid = (preset_id or "").strip().lower()
    preset = _PRESETS.get(pid)
    if preset is None:
        raise TeamConfigError(f"Unknown agent preset: {preset_id}. Available: {', '.join(sorted(_PRESETS))}")
    return preset


def create_team_from_yaml(
    team_id: str,
    *,
    config_path: Path,
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
) -> Team:
    normalized_id = (team_id or "").strip()
    if not normalized_id:
        raise TeamConfigError("Team id is required")

    teams_dir = config_path / "teams"
    yaml_path = teams_dir / f"{normalized_id}.yaml"
    yml_path = teams_dir / f"{normalized_id}.yml"
    if yaml_path.exists():
        path = yaml_path
    elif yml_path.exists():
        path = yml_path
    else:
        raise TeamConfigError(f"Team YAML not found: {normalized_id}")

    raw = _load_yaml(path)
    display_name = str(raw.get("name") or normalized_id).strip() or normalized_id
    show_members_responses = bool(raw.get("show_members_responses", True))

    team_policy = _parse_policy(raw.get("permissions"))
    agent_items = _parse_agents(raw.get("agents"))

    members = []
    for agent_cfg in agent_items:
        preset_id = agent_cfg.get("preset") or agent_cfg.get("id") or agent_cfg.get("agent")
        preset = _get_preset(str(preset_id))

        name = str(agent_cfg.get("name") or preset.name)
        role = str(agent_cfg.get("role") or preset.role)
        extra_instructions = agent_cfg.get("instructions")
        if isinstance(extra_instructions, str):
            instructions = preset.instructions + [extra_instructions]
        elif isinstance(extra_instructions, list):
            instructions = preset.instructions + [str(x) for x in extra_instructions if str(x).strip()]
        else:
            instructions = preset.instructions

        agent_policy = _parse_policy(agent_cfg.get("permissions")) or preset.tool_policy
        if team_policy is not None:
            agent_policy = ToolPolicy(
                allow_shell=agent_policy.allow_shell and team_policy.allow_shell,
                allow_file_write=agent_policy.allow_file_write and team_policy.allow_file_write,
                allow_python=agent_policy.allow_python and team_policy.allow_python,
                confirm_file_write=agent_policy.confirm_file_write or team_policy.confirm_file_write,
            )

        members.append(
            create_adorable_agent(
                db=db,
                session_summary_manager=session_summary_manager,
                compression_manager=compression_manager,
                name=name,
                role=role,
                instructions=instructions,
                tool_policy=agent_policy,
            )
        )

    return Team(
        id=normalized_id.lower(),
        name=display_name,
        model=OpenAILike(id=settings.model_id, api_key=settings.api_key, base_url=settings.base_url),
        members=members,
        markdown=True,
        show_members_responses=show_members_responses,
        instructions=[f"You are the {display_name} Team. Collaborate to complete the user request."],
    )
