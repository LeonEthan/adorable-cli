import os

from agno.compression.manager import CompressionManager
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAILike
from agno.session.summary import SessionSummaryManager
from agno.utils.log import configure_agno_logging

from deepagents_cli.agent.main_agent import create_deepagents_agent
from deepagents_cli.config import MEM_DB_PATH


def configure_logging() -> None:
    """Configure Agno logging using built-in helpers and env flags.

    Prefer Agno's native logging configuration over custom wrappers.
    """
    try:
        # Default log levels via environment (respected by Agno)
        os.environ.setdefault("AGNO_LOG_LEVEL", "WARNING")
        os.environ.setdefault("AGNO_TOOLS_LOG_LEVEL", "WARNING")
        # Initialize Agno logging with defaults
        configure_agno_logging()
    except Exception:
        # Non-fatal if logging configuration fails
        pass


def build_agent():
    """
    Builds the DeepAgents Single Agent.
    """
    # Model id can be customized via env MODEL_ID, else defaults
    model_id = os.environ.get("DEEPAGENTS_MODEL_ID", "gpt-5-mini")

    # Read API key and base URL from environment (supports OpenAI-compatible providers)
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("BASE_URL")

    # Summary model id can be customized via FAST_MODEL_ID (or DEEPAGENTS_FAST_MODEL_ID)
    fast_model_id = (
        os.environ.get("FAST_MODEL_ID") or os.environ.get("DEEPAGENTS_FAST_MODEL_ID") or model_id
    )

    # Shared user memory database (not fully utilized by Team class yet, but good to have)
    db = SqliteDb(db_file=str(MEM_DB_PATH))

    # Debug configuration from environment
    agno_debug_env = os.environ.get("AGNO_DEBUG", "").strip().lower()
    debug_mode = agno_debug_env in {"1", "true", "yes", "on"}
    debug_level_val = os.environ.get("AGNO_DEBUG_LEVEL", "")
    try:
        debug_level = int(debug_level_val) if debug_level_val else None
    except Exception:
        debug_level = None

    # Configure a dedicated fast model for session summaries if provided
    # Configure SessionSummaryManager to avoid JSON/structured outputs to prevent parsing warnings
    session_summary_manager = SessionSummaryManager(
        model=OpenAILike(
            id=fast_model_id,
            api_key=api_key,
            base_url=base_url,
            # Smaller cap is sufficient for summaries; providers may ignore
            max_tokens=4096,
            # Force plain-text outputs for summaries to avoid JSON parsing attempts
            supports_native_structured_outputs=False,
            supports_json_schema_outputs=False,
        ),
        # Ask for a plain-text summary only; no JSON or lists
        session_summary_prompt=(
            "Provide a concise plain-text summary of the recent conversation. "
            "Do not return JSON, XML, lists, or keys. Return one short paragraph."
        ),
    )

    # Configure Custom Compression Manager
    compression_manager = CompressionManager(
        model=OpenAILike(id=model_id, api_key=api_key, base_url=base_url),
        compress_tool_results=True,
        compress_tool_results_limit=10,
        compress_tool_call_instructions=(
            "Compress tool outputs for data science workflows. Preserve metrics, numbers, dates, "
            "dataset column names, shapes, file paths, URLs, identifiers, error tracebacks, "
            "model parameters and scores, and key findings. Remove boilerplate, redundant "
            "formatting, and generic background. Return concise plain text."
        ),
    )

    # Create the Single Agent
    agent = create_deepagents_agent(
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        debug_mode=debug_mode,
        debug_level=debug_level,
        db=db,
        session_summary_manager=session_summary_manager,
        compression_manager=compression_manager,
    )

    return agent
