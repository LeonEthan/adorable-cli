"""Prompt engineering system for Claude Code-style agents.

Implements aggressive conciseness, psychological techniques, and
adaptive prompting based on the blog post analysis.
"""

from adorable_cli.prompts.engineering import (
    PromptEngineer,
    PromptStyle,
    ConcisenessEnforcer,
    PromptMetrics,
)
from adorable_cli.prompts.templates import (
    get_system_prompt,
    get_tool_instructions,
    get_error_prompt,
    get_recovery_prompt,
)
from adorable_cli.prompts.psychological import (
    ConfidenceCalibrator,
    UncertaintyHandler,
    ErrorFraming,
)

__all__ = [
    # Engineering
    "PromptEngineer",
    "PromptStyle",
    "ConcisenessEnforcer",
    "PromptMetrics",
    # Templates
    "get_system_prompt",
    "get_tool_instructions",
    "get_error_prompt",
    "get_recovery_prompt",
    # Psychological
    "ConfidenceCalibrator",
    "UncertaintyHandler",
    "ErrorFraming",
]
