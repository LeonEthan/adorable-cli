from pathlib import Path
from typing import Any

from agno.agent import Agent
from agno.models.openai import OpenAILike
from agno.tools.mcp import MultiMCPTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.file import FileTools
from agno.tools.python import PythonTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.shell import ShellTools

from adorable_cli.agent.prompts import AGENT_INSTRUCTIONS, AGENT_ROLE
from adorable_cli.agent.policy import ToolPolicy, apply_tool_policy
from adorable_cli.settings import settings
from adorable_cli.tools.todo_tools import TodoTools
from adorable_cli.tools.vision_tool import create_image_understanding_tool


def create_adorable_agent(
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
    *,
    name: str = "Adorable Agent",
    role: str = AGENT_ROLE,
    instructions: list[str] = AGENT_INSTRUCTIONS,
    tool_policy: ToolPolicy | None = None,
    extra_tools: list[Any] | None = None,
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
        MultiMCPTools(
            commands=[
                "uvx mcp-server-fetch",
                "npx -y @playwright/mcp@latest",
            ],
            urls=["https://docs.agno.com/mcp"],
            urls_transports=["streamable-http"],
        ),
        create_image_understanding_tool(),
        TodoTools(),
    ]

    if extra_tools:
        tools.extend(extra_tools)

    # Create the Agent
    agent = Agent(
        name=name,
        model=OpenAILike(
            id=settings.model_id, api_key=settings.api_key, base_url=settings.base_url
        ),
        tools=tools,
        role=role,
        instructions=instructions,
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

    apply_tool_policy(agent, tool_policy or ToolPolicy())

    return agent
