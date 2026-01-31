"""Prompt templates with aggressive conciseness.

Implements Claude Code's principles:
- Aggressive conciseness
- Task-relevant repetition
- Clear tool boundaries
"""

from __future__ import annotations

from typing import Any


def get_system_prompt(
    role: str = "autonomous_agent",
    enable_reasoning: bool = True,
    context_info: dict[str, Any] | None = None,
) -> str:
    """Generate the main system prompt.

    Args:
        role: Agent role ("autonomous_agent", "file_editor", etc.)
        enable_reasoning: Whether to include reasoning tool instructions
        context_info: Additional context (cwd, files, etc.)

    Returns:
        System prompt string
    """
    parts = []

    # Core identity - minimal
    parts.append(_get_identity(role))

    # Operating mode - interleaved reasoning
    if enable_reasoning:
        parts.append(_get_reasoning_mode())

    # Critical rules - repeated for emphasis
    parts.append(_get_critical_rules())

    # Context information
    if context_info:
        parts.append(_format_context(context_info))

    # Completion rule
    parts.append(_get_completion_rule())

    return "\n\n".join(parts)


def _get_identity(role: str) -> str:
    """Get identity section."""
    identities = {
        "autonomous_agent": """# Adorable

Autonomous CLI agent. File system, shell, Python access. Operate in working directory.""",

        "file_editor": """# File Editor

Edit files with precision. Read before edit. Verify after.""",

        "researcher": """# Research Agent

Find information. Use search tools. Cite sources.""",

        "debugger": """# Debug Agent

Diagnose issues methodically. Never guess. Verify causes.""",
    }

    return identities.get(role, identities["autonomous_agent"])


def _get_reasoning_mode() -> str:
    """Get reasoning mode instructions."""
    return """## Mode: Interleaved Reasoning

TWO TOOL CATEGORIES:

1. REASONING: think, analyze
2. ACTION: FileTools, ShellTools, PythonTools, SearchTools

PATTERN: Reason → Act → Analyze → Repeat

CRITICAL: Never combine tools. One tool per call."""


def _get_critical_rules() -> str:
    """Get critical rules - repeated at decision points."""
    return """## Rules

CRITICAL: Exact tool names only. No hallucination.
CRITICAL: Read before edit.
CRITICAL: One tool call per step.
CRITICAL: Never guess. Verify first."""


def _format_context(context_info: dict[str, Any]) -> str:
    """Format context information concisely."""
    parts = ["## Context"]

    if "cwd" in context_info:
        parts.append(f"cwd: {context_info['cwd']}")

    if "files" in context_info:
        files = context_info["files"]
        if len(files) <= 5:
            parts.append(f"files: {', '.join(files)}")
        else:
            parts.append(f"files: {len(files)} items")

    if "git_branch" in context_info:
        parts.append(f"git: {context_info['git_branch']}")

    return "\n".join(parts)


def _get_completion_rule() -> str:
    """Get completion instructions."""
    return """## Completion

Task complete → Stop. Output result. No tool calls."""


def get_tool_instructions(tools: list[dict[str, Any]] | None = None) -> str:
    """Get tool instructions formatted concisely.

    Args:
        tools: List of available tools

    Returns:
        Formatted tool instructions
    """
    if not tools:
        return """## Available Tools

FileTools: list_files, read_file, save_file, search_files
ShellTools: run_shell_command
PythonTools: run_python_code
SearchTools: duckduckgo_search
Reasoning: think, analyze"""

    lines = ["## Tools"]

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for tool in tools:
        cat = tool.get("category", "General")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(tool)

    for category, cat_tools in by_category.items():
        lines.append(f"\n{category}:")
        for tool in cat_tools:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            # One-line description
            desc = desc.split(".")[0] if "." in desc else desc
            lines.append(f"  {name}: {desc}")

    lines.append("\nUse exact names. One per call.")

    return "\n".join(lines)


def get_error_prompt(
    error: str,
    error_type: str = "general",
    recovery_hint: str = "",
) -> str:
    """Generate an error recovery prompt.

    Uses prescriptive, not descriptive framing.

    Args:
        error: The error message
        error_type: Type of error ("tool", "format", "validation")
        recovery_hint: Optional hint for recovery

    Returns:
        Error recovery prompt
    """
    parts = ["ERROR. Fix and continue."]

    if error_type == "tool":
        parts.append("Tool error. Check name and arguments.")
    elif error_type == "format":
        parts.append("Format error. Check JSON/tool format.")
    elif error_type == "validation":
        parts.append("Validation error. Check parameters.")

    parts.append(f"Error: {error}")

    if recovery_hint:
        parts.append(f"Hint: {recovery_hint}")

    parts.extend([
        "",
        "Steps:",
        "1. Analyze error",
        "2. Fix issue",
        "3. Continue",
    ])

    return "\n".join(parts)


def get_recovery_prompt(
    consecutive_errors: int = 1,
    last_error: str = "",
) -> str:
    """Generate recovery prompt after multiple errors.

    Args:
        consecutive_errors: Number of consecutive errors
        last_error: The last error message

    Returns:
        Recovery prompt
    """
    if consecutive_errors == 0:
        return ""

    parts = []

    if consecutive_errors == 1:
        parts.append("Fix error and continue.")
    elif consecutive_errors == 2:
        parts.append("Second error. Slow down. Verify each step.")
    else:
        parts.append(f"Multiple errors ({consecutive_errors}). Simplify. Take smaller steps.")

    if last_error:
        # Extract key error info
        short_error = last_error.split("\n")[0][:100]
        parts.append(f"Last error: {short_error}")

    parts.extend([
        "",
        "Recovery:",
        "1. Analyze what went wrong",
        "2. Try a different approach",
        "3. Use simpler steps",
    ])

    return "\n".join(parts)


def get_first_turn_prompt(task_description: str = "") -> str:
    """Get prompt for first turn of conversation.

    Args:
        task_description: User's task/request

    Returns:
        First turn prompt
    """
    parts = [
        "First turn. Start with reasoning.",
        "",
    ]

    if task_description:
        parts.append(f"Task: {task_description}")

    parts.extend([
        "",
        "Step 1: Use think() to plan",
        "Step 2: Execute with one action tool",
        "Step 3: Use analyze() to interpret",
    ])

    return "\n".join(parts)


def get_think_prompt(title: str, thought: str, action: str = "") -> str:
    """Format a think tool call for the prompt.

    Args:
        title: Think title
        thought: Thought content
        action: Action description

    Returns:
        Formatted think prompt section
    """
    parts = [
        "think(",
        f'    title="{title}",',
        f'    thought="{thought}",',
    ]

    if action:
        parts.append(f'    action="{action}"')

    parts.append(")")

    return "\n".join(parts)


def get_analyze_prompt(
    title: str,
    result: str,
    analysis: str,
    next_action: str = "",
) -> str:
    """Format an analyze tool call for the prompt.

    Args:
        title: Analysis title
        result: Result to analyze
        analysis: Analysis content
        next_action: Next action description

    Returns:
        Formatted analyze prompt section
    """
    parts = [
        "analyze(",
        f'    title="{title}",',
        f'    result="{result[:200]}..."' if len(result) > 200 else f'    result="{result}"',
        f'    analysis="{analysis}",',
    ]

    if next_action:
        parts.append(f'    next_action="{next_action}"')

    parts.append(")")

    return "\n".join(parts)


def get_confirmation_prompt(
    action: str,
    details: str = "",
    risk_level: str = "medium",
) -> str:
    """Get confirmation prompt for risky actions.

    Args:
        action: Action requiring confirmation
        details: Additional details
        risk_level: "low", "medium", "high"

    Returns:
        Confirmation prompt
    """
    parts = ["CONFIRMATION REQUIRED"]

    if risk_level == "high":
        parts.append("⚠️ HIGH RISK")
    elif risk_level == "medium":
        parts.append("⚡ Medium risk")

    parts.append(f"Action: {action}")

    if details:
        parts.append(f"Details: {details}")

    parts.append("\nConfirm to proceed.")

    return "\n".join(parts)


def compress_for_emergency(max_tokens: int = 500) -> str:
    """Get ultra-compressed system prompt for emergency fallback.

    When hitting token limits, use this minimal prompt.

    Args:
        max_tokens: Available token budget

    Returns:
        Compressed prompt
    """
    return """# Adorable

Autonomous CLI agent.

CRITICAL: Exact tool names only.
CRITICAL: Read before edit.
CRITICAL: One tool per call.
CRITICAL: Never guess.

Mode: think → act → analyze → repeat."""
