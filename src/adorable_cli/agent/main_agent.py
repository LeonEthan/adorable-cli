from pathlib import Path
from typing import Any, Optional

from agno.agent import Agent
from agno.models.openai import OpenAILike
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.file import FileTools
from agno.tools.python import PythonTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.shell import ShellTools
from agno.tools.tavily import TavilyTools

from adorable_cli.hooks.context_guard import ensure_context_within_window, restore_context_settings
from adorable_cli.prompt import MAIN_AGENT_INSTRUCTIONS
from adorable_cli.tools.vision_tool import create_image_understanding_tool


def create_adorable_agent(
    model_id: str,
    api_key: Optional[str],
    base_url: Optional[str],
    debug_mode: bool = False,
    debug_level: Optional[int] = None,
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
) -> Agent:
    """
    Creates a single autonomous agent with all capabilities.
    """

    # Initialize all tools
    tools = [
        FileTools(base_dir=Path.cwd(), all=True),
        TavilyTools(),
        Crawl4aiTools(),
        PythonTools(base_dir=Path.cwd()),
        ShellTools(base_dir=Path.cwd()),
        create_image_understanding_tool(),
        ReasoningTools(add_instructions=True),
    ]

    # Create the Agent
    agent = Agent(
        name="Adorable Agent",
        model=OpenAILike(id=model_id, api_key=api_key, base_url=base_url),
        tools=tools,
        role="You are a universal autonomous agent capable of planning, research, and complex execution.",
        instructions=MAIN_AGENT_INSTRUCTIONS,
        add_datetime_to_context=True,
        # todo list management using session state
        session_state={
            "todos": [],
        },
        enable_agentic_state=True,
        add_session_state_to_context=True,
        # memory
        db=db,
        # Long-term memory
        enable_session_summaries=True,
        session_summary_manager=session_summary_manager,
        add_session_summary_to_context=True,
        # Short-term memory
        add_history_to_context=True,
        num_history_runs=3,
        max_tool_calls_from_history=3,
        # output format
        markdown=True,
        # built-in debug toggles
        debug_mode=debug_mode,
        **({"debug_level": debug_level} if debug_level is not None else {}),
        # Retry strategy
        exponential_backoff=True,
        retries=2,
        delay_between_retries=1,
        # Context compression
        compress_tool_results=True,
        compression_manager=compression_manager,
        # Context guard hooks
        pre_hooks=[ensure_context_within_window],
        post_hooks=[restore_context_settings],
    )

    # Apply confirmation logic
    python_names = {"execute_python_code", "run_python_code"}
    shell_names = {"run_shell_command"}

    target_true = python_names | shell_names

    for tk in agent.tools:
        functions = getattr(tk, "functions", {})
        if not isinstance(functions, dict):
            continue
        for name, f in functions.items():
            if name in target_true:
                try:
                    setattr(f, "requires_confirmation", True)
                except Exception:
                    pass

    return agent
