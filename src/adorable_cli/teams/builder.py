from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agno.models.openai import OpenAILike
from agno.team import Team

from adorable_cli.agent.main_agent import create_adorable_agent
from adorable_cli.agent.prompts import AGENT_INSTRUCTIONS, AGENT_ROLE
from adorable_cli.config import CONFIG_PATH
from adorable_cli.settings import settings


BUILTIN_TEAM_IDS: tuple[str, ...] = ("coding", "research", "planning")


@dataclass(frozen=True)
class TeamDefinition:
    team_id: str
    display_name: str


BUILTIN_TEAMS: tuple[TeamDefinition, ...] = (
    TeamDefinition(team_id="coding", display_name="coding"),
    TeamDefinition(team_id="research", display_name="research"),
    TeamDefinition(team_id="planning", display_name="planning"),
)


def list_builtin_team_ids() -> list[str]:
    return [t.team_id for t in BUILTIN_TEAMS]


def list_configured_team_ids(config_path: Path = CONFIG_PATH) -> list[str]:
    teams_dir = config_path / "teams"
    if not teams_dir.exists():
        return []

    names: set[str] = set()
    for p in teams_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".yaml", ".yml"):
            continue
        if p.stem.strip():
            names.add(p.stem.strip())
    return sorted(names)


def list_team_ids(config_path: Path = CONFIG_PATH) -> list[str]:
    ids = set(list_builtin_team_ids())
    ids.update(list_configured_team_ids(config_path=config_path))
    return sorted(ids)


def create_team(
    team_id: str,
    *,
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
) -> Team:
    normalized = (team_id or "").strip().lower()
    if normalized == "coding":
        return create_coding_team(
            db=db,
            session_summary_manager=session_summary_manager,
            compression_manager=compression_manager,
        )
    if normalized == "research":
        return create_research_team(
            db=db,
            session_summary_manager=session_summary_manager,
            compression_manager=compression_manager,
        )
    if normalized == "planning":
        return create_planning_team(
            db=db,
            session_summary_manager=session_summary_manager,
            compression_manager=compression_manager,
        )
    raise ValueError(f"Unknown team: {team_id}. Available: {', '.join(list_team_ids())}")


def _mk_instructions(*extra: str) -> list[str]:
    instructions = list(AGENT_INSTRUCTIONS)
    instructions.extend([e for e in extra if e and e.strip()])
    return instructions


def _mk_team_model() -> OpenAILike:
    return OpenAILike(id=settings.model_id, api_key=settings.api_key, base_url=settings.base_url)


def create_coding_team(
    *,
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
) -> Team:
    planner = create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        name="Planner",
        role=f"{AGENT_ROLE}. Primary focus: planning and decomposition.",
        instructions=_mk_instructions(
            "You are the Planner. Break the task into steps, identify risks, and propose a plan. "
            "Prefer analysis and clear next actions over implementation details."
        ),
    )
    coder = create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        name="Coder",
        role=f"{AGENT_ROLE}. Primary focus: implementation.",
        instructions=_mk_instructions(
            "You are the Coder. Implement the requested changes with minimal diffs. "
            "Prefer using existing patterns and keep codebase conventions."
        ),
    )
    tester = create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        name="Tester",
        role=f"{AGENT_ROLE}. Primary focus: tests and validation.",
        instructions=_mk_instructions(
            "You are the Tester. Add or update unit tests for changes. "
            "Prefer deterministic tests and validate expected behavior."
        ),
    )

    return Team(
        id="coding",
        name="coding",
        model=_mk_team_model(),
        members=[planner, coder, tester],
        markdown=True,
        show_members_responses=True,
        instructions=[
            "You are the Coding Team. Collaborate to plan, implement, and validate changes.",
            "Planner proposes the approach, Coder implements, Tester verifies with tests.",
        ],
    )


def create_research_team(
    *,
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
) -> Team:
    searcher = create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        name="Searcher",
        role=f"{AGENT_ROLE}. Primary focus: gather information and evidence.",
        instructions=_mk_instructions(
            "You are the Searcher. Find relevant facts in code, docs, and reliable sources. "
            "Prefer precise citations and avoid speculation."
        ),
    )
    analyst = create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        name="Analyst",
        role=f"{AGENT_ROLE}. Primary focus: analysis and synthesis.",
        instructions=_mk_instructions(
            "You are the Analyst. Synthesize findings into a clear answer or recommendation. "
            "Highlight tradeoffs and constraints."
        ),
    )
    writer = create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        name="Writer",
        role=f"{AGENT_ROLE}. Primary focus: produce the final write-up.",
        instructions=_mk_instructions(
            "You are the Writer. Produce concise, well-structured output. "
            "Make results easy to scan and actionable."
        ),
    )

    return Team(
        id="research",
        name="research",
        model=_mk_team_model(),
        members=[searcher, analyst, writer],
        markdown=True,
        show_members_responses=True,
        instructions=[
            "You are the Research Team. Gather, analyze, and write up findings.",
            "Searcher gathers evidence, Analyst synthesizes, Writer finalizes the response.",
        ],
    )


def create_planning_team(
    *,
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
) -> Team:
    planner = create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        name="Planner",
        role=f"{AGENT_ROLE}. Primary focus: planning (read-only preference).",
        instructions=_mk_instructions(
            "You are the Planning Team. Prefer proposing plans and design decisions. "
            "Avoid editing files or running shell commands unless explicitly requested."
        ),
    )

    return Team(
        id="planning",
        name="planning",
        model=_mk_team_model(),
        members=[planner],
        markdown=True,
        show_members_responses=True,
        instructions=[
            "You are the Planning Team. Produce plans and architecture guidance.",
            "Prefer read-only analysis; only execute tools when explicitly requested.",
        ],
    )

