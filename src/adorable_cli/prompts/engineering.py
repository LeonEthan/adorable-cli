"""Prompt engineering with aggressive conciseness enforcement.

Claude Code's prompt engineering insights:
1. Aggressive conciseness - fewer tokens = faster, cheaper, better
2. Task-relevant repetition - repeat key constraints
3. Psychological techniques - "never guess", confidence calibration
4. Adaptive prompting - adjust based on context/state
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class PromptStyle(Enum):
    """Different prompt styles for different contexts."""

    CONCISE = "concise"      # Default: minimal tokens
    VERBOSE = "verbose"      # For complex tasks
    RECOVERY = "recovery"    # For error recovery
    FIRST_TURN = "first"     # First interaction


@dataclass
class PromptMetrics:
    """Metrics for prompt effectiveness."""

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    response_time_ms: float = 0.0
    retry_count: int = 0
    tool_hallucinations: int = 0
    format_errors: int = 0

    def record_response(self, prompt_len: int, completion_len: int, time_ms: float) -> None:
        """Record a response."""
        self.prompt_tokens += prompt_len
        self.completion_tokens += completion_len
        self.total_tokens += prompt_len + completion_len
        self.response_time_ms += time_ms


class ConcisenessEnforcer:
    """Enforces aggressive conciseness in prompts.

    Claude Code insight: "Aggressive conciseness pays off infinitely.
    Every token removed from the system prompt is forever free."
    """

    # Common filler words and phrases to remove
    FILLER_PATTERNS = [
        r"\bplease\b",
        r"\bkindly\b",
        r"\bfeel free to\b",
        r"\bdon't hesitate to\b",
        r"\bit is important to note that\b",
        r"\bit should be noted that\b",
        r"\bin order to\b",
        r"\bdue to the fact that\b",
        r"\bfor the purpose of\b",
        r"\bin the event that\b",
        r"\bat this point in time\b",
        r"\bwith regard to\b",
        r"\bin connection with\b",
        r"\byou are advised to\b",
        r"\bit is recommended that\b",
    ]

    # Redundant qualifiers
    REDUNDANT_QUALIFIERS = [
        r"\bvery\s+",
        r"\breally\s+",
        r"\bquite\s+",
        r"\bactually\s+",
        r"\bbasically\s+",
        r"\bsimply\s+",
        r"\bjust\s+",
    ]

    @classmethod
    def enforce(cls, text: str, aggressive: bool = True) -> str:
        """Enforce conciseness on text.

        Args:
            text: Input text
            aggressive: If True, apply more aggressive compression

        Returns:
            Concise version of text
        """
        result = text

        # Remove filler phrases
        for pattern in cls.FILLER_PATTERNS:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        if aggressive:
            # Remove redundant qualifiers
            for pattern in cls.REDUNDANT_QUALIFIERS:
                result = re.sub(pattern, "", result, flags=re.IGNORECASE)

            # Convert "You should X" -> "X"
            result = re.sub(
                r"\byou\s+should\s+",
                "",
                result,
                flags=re.IGNORECASE
            )

            # Remove excessive newlines
            result = re.sub(r"\n{3,}", "\n\n", result)

            # Remove trailing whitespace
            lines = [line.rstrip() for line in result.split("\n")]
            result = "\n".join(lines)

        return result.strip()

    @classmethod
    def count_tokens_saved(cls, original: str, compressed: str) -> int:
        """Estimate tokens saved."""
        # Rough approximation: 4 chars per token
        original_tokens = len(original) // 4
        compressed_tokens = len(compressed) // 4
        return original_tokens - compressed_tokens


class PromptEngineer:
    """Engineers prompts with Claude Code's techniques.

    Key principles:
    1. Conciseness - minimize tokens
    2. Repetition - repeat task-relevant constraints
    3. Psychological framing - "never guess", confidence calibration
    4. Adaptive - adjust based on context
    """

    def __init__(
        self,
        base_prompt: str,
        style: PromptStyle = PromptStyle.CONCISE,
        enable_metrics: bool = True,
    ):
        self.base_prompt = base_prompt
        self.style = style
        self.enable_metrics = enable_metrics
        self.metrics = PromptMetrics()
        self._turn_count = 0
        self._error_count = 0

    def engineer(
        self,
        context: dict[str, Any],
        task_type: str = "general",
    ) -> str:
        """Engineer a prompt for the given context.

        Args:
            context: Context information (tools, history, etc.)
            task_type: Type of task ("file_edit", "search", "debug", etc.)

        Returns:
            Engineered prompt
        """
        parts = []

        # Base system prompt
        parts.append(self.base_prompt)

        # Add task-specific repetitions
        task_repetitions = self._get_task_repetitions(task_type)
        if task_repetitions:
            parts.append(task_repetitions)

        # Add current turn context
        turn_context = self._get_turn_context()
        if turn_context:
            parts.append(turn_context)

        # Add working memory if present
        if "working_memory" in context:
            parts.append(context["working_memory"])

        # Add tool instructions
        if "tools" in context:
            tool_instructions = self._format_tool_instructions(context["tools"])
            parts.append(tool_instructions)

        # Combine and enforce conciseness
        prompt = "\n\n".join(parts)
        prompt = ConcisenessEnforcer.enforce(prompt, aggressive=True)

        self._turn_count += 1

        return prompt

    def _get_task_repetitions(self, task_type: str) -> str:
        """Get task-specific repeated constraints.

        Claude Code insight: "Task-relevant repetition is a feature, not a bug.
        Repeat critical constraints at the point of decision."
        """
        repetitions = {
            "file_edit": """
CRITICAL: Read file before editing.
CRITICAL: Use exact tool names only.
CRITICAL: One tool call per step.
""",
            "shell": """
CRITICAL: Never run destructive commands without confirmation.
CRITICAL: Verify command safety before execution.
""",
            "search": """
CRITICAL: Use exact search patterns.
CRITICAL: Read relevant files to understand context.
""",
            "debug": """
CRITICAL: Never guess at error causes.
CRITICAL: Verify with evidence before fixing.
""",
            "first_turn": """
CRITICAL: Start with reasoning, then action.
CRITICAL: Use exact tool names only.
CRITICAL: Interleaved pattern: think → act → analyze.
""",
        }

        return repetitions.get(task_type, "")

    def _get_turn_context(self) -> str:
        """Get context specific to current turn."""
        context_parts = []

        if self._turn_count == 0:
            context_parts.append("This is the first turn. Start with reasoning.")

        if self._error_count > 0:
            context_parts.append(
                f"Recent errors: {self._error_count}. Be careful."
            )

        return "\n".join(context_parts)

    def _format_tool_instructions(self, tools: list[dict[str, Any]]) -> str:
        """Format tool instructions concisely."""
        lines = ["## Tools (exact names only)"]

        for tool in tools:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            # Truncate description to first sentence
            if "." in desc:
                desc = desc[:desc.find(".") + 1]
            lines.append(f"- {name}: {desc}")

        return "\n".join(lines)

    def record_success(self) -> None:
        """Record a successful response."""
        self._error_count = max(0, self._error_count - 1)

    def record_error(
        self,
        error_type: str,
        details: str = "",
    ) -> None:
        """Record an error for adaptive prompting."""
        self._error_count += 1
        self.metrics.retry_count += 1

        if "hallucination" in error_type.lower():
            self.metrics.tool_hallucinations += 1
        elif "format" in error_type.lower():
            self.metrics.format_errors += 1

    def get_recovery_prompt(self, error: str, context: dict[str, Any]) -> str:
        """Generate a recovery prompt after errors.

        Uses "prescriptive, not descriptive" principle.
        """
        parts = [
            "ERROR OCCURRED. Correct and continue.",
            f"Error: {error}",
            "",
            "RECOVERY STEPS:",
            "1. Analyze the error",
            "2. Fix the issue",
            "3. Continue the task",
            "",
            "DO NOT apologize. DO NOT explain. Just fix.",
        ]

        # Add specific guidance based on error type
        if "tool" in error.lower() or "function" in error.lower():
            parts.append("CRITICAL: Use exact tool names only. Check spelling.")

        if "argument" in error.lower() or "parameter" in error.lower():
            parts.append("CRITICAL: Verify all required parameters.")

        return "\n".join(parts)

    def get_metrics(self) -> PromptMetrics:
        """Get prompt engineering metrics."""
        return self.metrics


class AdaptivePromptBuilder:
    """Builds prompts that adapt based on interaction history."""

    def __init__(self):
        self.history: list[dict[str, Any]] = []
        self.error_patterns: dict[str, int] = {}

    def add_interaction(
        self,
        prompt: str,
        response: str,
        success: bool,
        error: str = "",
    ) -> None:
        """Add an interaction to history."""
        self.history.append({
            "prompt_len": len(prompt),
            "response_len": len(response),
            "success": success,
            "error": error,
            "timestamp": time.time(),
        })

        if error:
            pattern = self._extract_error_pattern(error)
            self.error_patterns[pattern] = self.error_patterns.get(pattern, 0) + 1

    def _extract_error_pattern(self, error: str) -> str:
        """Extract a generalized error pattern."""
        # Simplify error message to find patterns
        pattern = error.lower()

        # Remove specific values
        pattern = re.sub(r"'[^']+'", "'X'", pattern)
        pattern = re.sub(r"\"[^\"]+\"", '"X"', pattern)

        # Common error types
        if "tool" in pattern and "not found" in pattern:
            return "tool_not_found"
        if "argument" in pattern:
            return "argument_error"
        if "format" in pattern or "json" in pattern:
            return "format_error"

        return "unknown"

    def build_adaptive_context(self) -> str:
        """Build adaptive context based on history."""
        if not self.history:
            return ""

        parts = []

        # Check for repeated errors
        repeated = [
            (p, c) for p, c in self.error_patterns.items()
            if c >= 2
        ]
        if repeated:
            parts.append("REPEATED ISSUES:")
            for pattern, count in repeated[:3]:
                parts.append(f"- {pattern} ({count}x)")

        # Check success rate
        recent = self.history[-10:]
        successes = sum(1 for h in recent if h["success"])
        if len(recent) >= 5 and successes < len(recent) // 2:
            parts.append("WARNING: Recent struggles. Simplify approach.")

        return "\n".join(parts)


# Utility functions


def create_engineered_prompt(
    base_prompt: str,
    context: dict[str, Any],
    task_type: str = "general",
) -> str:
    """Create an engineered prompt (convenience function)."""
    engineer = PromptEngineer(base_prompt)
    return engineer.engineer(context, task_type)


def compress_prompt_for_fallback(prompt: str, max_chars: int = 2000) -> str:
    """Compress a prompt for emergency fallback.

    When approaching token limits, aggressively compress the prompt.
    """
    if len(prompt) <= max_chars:
        return prompt

    # Extract critical sections
    critical_patterns = [
        r"## Critical.*?(?=##|\Z)",
        r"CRITICAL:.*",
        r"NEVER.*",
        r"ALWAYS.*",
    ]

    critical_parts = []
    remaining = prompt

    for pattern in critical_patterns:
        matches = re.findall(pattern, remaining, re.IGNORECASE | re.DOTALL)
        critical_parts.extend(matches)
        remaining = re.sub(pattern, "", remaining, flags=re.IGNORECASE | re.DOTALL)

    # Compress remaining
    compressed_remaining = ConcisenessEnforcer.enforce(remaining, aggressive=True)

    # Combine
    result = "\n".join(critical_parts) + "\n" + compressed_remaining

    if len(result) > max_chars:
        result = result[:max_chars - 50] + "\n..."

    return result
