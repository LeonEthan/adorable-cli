from typing import Any, Optional

from agno.models.openai import OpenAILike
from agno.team import Team
from agno.tools.reasoning import ReasoningTools

from adorable_cli.agent.subagents import (
    create_code_execution_agent,
    create_code_writer_agent,
    create_documentation_agent,
    create_file_search_agent,
    create_web_search_agent,
)
from adorable_cli.hooks.context_guard import ensure_context_within_window, restore_context_settings
from adorable_cli.prompt import ORCHESTRATOR_INSTRUCTIONS


def create_orchestrator_team(
    model_id: str,
    api_key: Optional[str],
    base_url: Optional[str],
    confirm_mode: str = "auto",
    debug_mode: bool = False,
    debug_level: Optional[int] = None,
    db: Any = None,
    session_summary_manager: Any = None,
    compression_manager: Any = None,
) -> Team:
    """
    Creates the Orchestrator Team with all subagents.
    """

    # 1. Create Subagents
    file_search = create_file_search_agent(model_id, api_key, base_url)
    web_search = create_web_search_agent(model_id, api_key, base_url)
    code_writer = create_code_writer_agent(model_id, api_key, base_url)
    code_exec = create_code_execution_agent(model_id, api_key, base_url, confirm_mode)
    documentation = create_documentation_agent(model_id, api_key, base_url)

    # Apply confirmation logic to code_exec agent tools
    # (Reusing the logic from main/builder, simplified here)
    python_names = {"execute_python_code", "run_python_code"}
    shell_names = {"run_shell_command"}

    target_true = set()
    if confirm_mode == "normal":
        target_true = python_names | shell_names | {"save_file"}
    elif confirm_mode == "auto":
        target_true = python_names | shell_names

    if target_true:
        for tk in code_exec.tools:
            functions = getattr(tk, "functions", {})
            if not isinstance(functions, dict):
                continue
            for name, f in functions.items():
                if name in target_true:
                    try:
                        setattr(f, "requires_confirmation", True)
                    except Exception:
                        pass

    # 2. Create the Team (Orchestrator)
    team = Team(
        name="Adorable Orchestrator",
        model=OpenAILike(id=model_id, api_key=api_key, base_url=base_url),
        members=[
            file_search,
            web_search,
            code_writer,
            code_exec,
            documentation,
        ],
        role="You are the Orchestrator. Receive high-level goals, break them down, and delegate to subagents.",
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        # Reasoning tools for the orchestrator to plan
        tools=[ReasoningTools(add_instructions=True)],
        show_members_responses=True,  # Important to see subagent work
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

    return team
