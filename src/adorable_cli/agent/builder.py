import os

from agno.compression.manager import CompressionManager
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAILike
from agno.session.summary import SessionSummaryManager
from agno.utils.log import configure_agno_logging

from adorable_cli.agent.main_agent import create_adorable_agent
from adorable_cli.agent.patches import apply_patches
from adorable_cli.agent.prompts import COMPRESSION_INSTRUCTIONS, SESSION_SUMMARY_PROMPT
from adorable_cli.settings import settings


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


def build_agent():
    db, session_summary_manager, compression_manager = _build_shared_resources()
    return create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
    )


def build_component(team: str | None = None):
    db, session_summary_manager, compression_manager = _build_shared_resources()

    if team is None or not str(team).strip():
        return create_adorable_agent(
            db=db,
            session_summary_manager=session_summary_manager,
            compression_manager=compression_manager,
        )

    from adorable_cli.teams.builder import create_team

    return create_team(
        team,
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
    )
