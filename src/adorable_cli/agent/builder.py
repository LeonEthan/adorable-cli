import os
from pathlib import Path

from agno.compression.manager import CompressionManager
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAILike
from agno.session.summary import SessionSummaryManager
from agno.utils.log import configure_agno_logging

from adorable_cli.agent.main_agent import create_adorable_agent
from adorable_cli.agent.patches import apply_patches
from adorable_cli.agent.prompts import COMPRESSION_INSTRUCTIONS, SESSION_SUMMARY_PROMPT
from adorable_cli.settings import settings
from adorable_cli.config import CONFIG_PATH
from adorable_cli.ext.tools import ToolsLoader
from adorable_cli.ext.skills import SkillsLoader


def configure_logging() -> None:
    """Configure Agno logging using built-in helpers and env flags.

    Prefer Agno's native logging configuration over custom wrappers.
    """
    # Default log levels via environment (respected by Agno)
    os.environ.setdefault("AGNO_LOG_LEVEL", "WARNING")
    os.environ.setdefault("AGNO_TOOLS_LOG_LEVEL", "WARNING")
    # Initialize Agno logging with defaults
    configure_agno_logging()


def _build_shared_resources() -> tuple[SqliteDb, SessionSummaryManager, CompressionManager]:
    apply_patches()

    db = SqliteDb(db_file=str(settings.mem_db_path))

    fast_model_id = settings.fast_model_id or settings.model_id

    session_summary_manager = SessionSummaryManager(
        model=OpenAILike(
            id=fast_model_id,
            api_key=settings.api_key,
            base_url=settings.base_url,
            max_tokens=8192,
            supports_native_structured_outputs=False,
            supports_json_schema_outputs=False,
        ),
        session_summary_prompt=SESSION_SUMMARY_PROMPT,
    )

    compression_manager = CompressionManager(
        model=OpenAILike(id=fast_model_id, api_key=settings.api_key, base_url=settings.base_url),
        compress_tool_results=True,
        compress_tool_results_limit=50,
        compress_tool_call_instructions=COMPRESSION_INSTRUCTIONS,
    )

    return db, session_summary_manager, compression_manager


def _load_extensions() -> list:
    extra_tools = []
    # Load Tools
    tools_loader = ToolsLoader(CONFIG_PATH / "tools")
    extra_tools.extend(tools_loader.load_tools())
    
    # Load Skills (as tools)
    skills_loader = SkillsLoader(CONFIG_PATH / "skills")
    extra_tools.extend(skills_loader.load_skills())

    claude_skills_dir = Path.home() / ".claude" / "skills"
    if claude_skills_dir.exists():
        extra_tools.extend(SkillsLoader(claude_skills_dir).load_skills())
    
    return _dedupe_tools(extra_tools)


def _dedupe_tools(tools: list) -> list:
    seen: set[tuple[str | None, str, str]] = set()
    unique: list = []
    for tool in tools:
        key = (
            getattr(tool, "name", None),
            tool.__class__.__module__,
            tool.__class__.__name__,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(tool)
    return unique


def build_agent():
    db, session_summary_manager, compression_manager = _build_shared_resources()
    extra_tools = _load_extensions()
    return create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        extra_tools=extra_tools,
    )


def build_component(team: str | None = None):
    db, session_summary_manager, compression_manager = _build_shared_resources()
    extra_tools = _load_extensions()

    if team is None or not str(team).strip():
        return create_adorable_agent(
            db=db,
            session_summary_manager=session_summary_manager,
            compression_manager=compression_manager,
            extra_tools=extra_tools,
        )

    from adorable_cli.teams.builder import create_team

    return create_team(
        team,
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
        # Note: Teams might not support extra_tools yet in create_team signature
        # We need to check create_team
    )
