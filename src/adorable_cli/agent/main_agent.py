from pathlib import Path
from typing import Any

from agno.agent import Agent
from agno.models.openai import OpenAILike
from agno.tools.mcp import MCPTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.file import FileTools
from agno.tools.python import PythonTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.shell import ShellTools

from adorable_cli.agent.prompts import AGENT_INSTRUCTIONS, AGENT_ROLE
from adorable_cli.settings import settings
from adorable_cli.tools.todo_tools import TodoTools
from adorable_cli.tools.vision_tool import create_image_understanding_tool


def create_adorable_agent(
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
) -> Agent:
    """
    Creates a single autonomous agent with all capabilities.

    Note: MCPTools (fetch) connection is managed automatically by the Agent.
    """

    # Initialize all tools
    tools = [
        ReasoningTools(add_instructions=True),
        FileTools(base_dir=Path.cwd()),
        ShellTools(base_dir=Path.cwd()),
        PythonTools(
            base_dir=Path.cwd(),
            include_tools=["run_python_code"],
        ),
        DuckDuckGoTools(),
        MCPTools(command="uvx mcp-server-fetch"),
        create_image_understanding_tool(),
        TodoTools(),
    ]

    # Create the Agent
    agent = Agent(
        name="Adorable Agent",
        model=OpenAILike(
            id=settings.model_id, api_key=settings.api_key, base_url=settings.base_url
        ),
        tools=tools,
        role=AGENT_ROLE,
        instructions=AGENT_INSTRUCTIONS,
        add_datetime_to_context=True,
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
        debug_mode=settings.debug_mode,
        # Retry strategy
        exponential_backoff=True,
        retries=2,
        delay_between_retries=1,
        # Context compression
        compress_tool_results=True,
        compression_manager=compression_manager,
    )

    # Enable confirmation for shell commands
    # The handler auto-approves safe operations, only prompts for deletion commands
    # See handle_tool_confirmation in interactive.py for the logic
    shell_names = {"run_shell_command"}

    for tk in agent.tools:
        functions = getattr(tk, "functions", {})
        if not isinstance(functions, dict):
            continue
        for name, f in functions.items():
            if name in shell_names:
                try:
                    setattr(f, "requires_confirmation", True)
                except Exception:
                    pass

    return agent
