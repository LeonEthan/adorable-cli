import asyncio
import os

from agno.compression.manager import CompressionManager
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAILike
from agno.session.summary import SessionSummaryManager
from agno.utils.log import configure_agno_logging
from agno.tools.mcp import MCPTools

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


async def _build_agent_async():
    """
    Builds the Adorable Single Agent with proper MCP initialization.
    This is an internal async function that handles MCPTools connection.
    """
    # Apply monkey patches for robust tool execution
    apply_patches()

    # Shared user memory database (not fully utilized by Team class yet, but good to have)
    db = SqliteDb(db_file=str(settings.mem_db_path))

    # Configure a dedicated fast model for session summaries if provided
    # Configure SessionSummaryManager to avoid JSON/structured outputs to prevent parsing warnings
    fast_model_id = settings.fast_model_id or settings.model_id

    session_summary_manager = SessionSummaryManager(
        model=OpenAILike(
            id=fast_model_id,
            api_key=settings.api_key,
            base_url=settings.base_url,
            # Smaller cap is sufficient for summaries; providers may ignore
            max_tokens=8192,
            # Force plain-text outputs for summaries to avoid JSON parsing attempts
            supports_native_structured_outputs=False,
            supports_json_schema_outputs=False,
        ),
        # Ask for a plain-text summary only; no JSON or lists
        session_summary_prompt=SESSION_SUMMARY_PROMPT,
    )

    # Configure Custom Compression Manager
    compression_manager = CompressionManager(
        model=OpenAILike(id=fast_model_id, api_key=settings.api_key, base_url=settings.base_url),
        compress_tool_results=True,
        compress_tool_results_limit=50,
        compress_tool_call_instructions=COMPRESSION_INSTRUCTIONS,
    )

    # Create the Single Agent
    agent = create_adorable_agent(
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
    )

    # Connect MCP tools (fetch) before returning agent
    for tool in agent.tools:
        if isinstance(tool, MCPTools):
            try:
                await tool.connect()
            except Exception as e:
                print(f"Warning: Failed to connect MCPTools: {e}")

    return agent


def build_agent():
    """
    Builds the Adorable Single Agent.
    Handles async MCP initialization within a sync context.
    """
    # Use asyncio to run the async build process
    return asyncio.run(_build_agent_async())
