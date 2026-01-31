"""Agent context for loop execution state.

Simple wrapper that combines execution state with context assembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from adorable_cli.context.assembler import ContextAssembler, PriorityLevel
from adorable_cli.models.messages import CliMessage


@dataclass
class ContextWindow:
    """Context window pressure tracking."""

    max_tokens: int = 200_000
    compaction_threshold: float = 0.85
    current_tokens: int = 0

    def should_compact(self) -> bool:
        """Check if context should be compacted."""
        return self.current_tokens > (self.max_tokens * self.compaction_threshold)


@dataclass
class SimpleHistory:
    """Simple message history tracker."""

    messages: list[CliMessage] = field(default_factory=list)

    def add_message(self, message: CliMessage) -> None:
        """Add a message to history."""
        self.messages.append(message)


@dataclass
class ToolRegistry:
    """Simple tool registry."""

    tools: dict[str, Any] = field(default_factory=dict)

    def is_dangerous(self, tool_name: str) -> bool:
        """Check if tool is dangerous."""
        # Check for destructive shell commands
        dangerous_patterns = ["rm -rf", "sudo", "chmod -R 000", "mkfs", "dd if="]
        return any(p in tool_name for p in dangerous_patterns)

    def is_read_only(self, tool_name: str) -> bool:
        """Check if tool is read-only."""
        read_only_tools = ["read_file", "list_files", "search_files", "grep"]
        return tool_name in read_only_tools

    def get(self, tool_name: str) -> Any:
        """Get tool definition."""
        return self.tools.get(tool_name)


class AgentContext:
    """Execution context for the agent loop.

    Combines state management with context assembly capabilities.
    """

    def __init__(
        self,
        cwd: Optional[Path] = None,
        max_tokens: int = 200_000,
    ):
        self.cwd = cwd or Path.cwd()
        self.turn_count = 0
        self.window = ContextWindow(max_tokens=max_tokens)
        self.history = SimpleHistory()
        self.tools = ToolRegistry()
        self.assembler = ContextAssembler(max_tokens=max_tokens)

        # File cache for read-before-edit
        self._file_cache: dict[Path, str] = {}

    def build_context_messages(self) -> list[dict[str, Any]]:
        """Build context messages for API call."""
        messages = []

        # Add system prompt if available
        # TODO: Load from actual system prompt

        # Add history messages
        for msg in self.history.messages:
            messages.append({"role": msg.role, "content": msg.content})

        return messages

    def cache_file(self, path: Path) -> None:
        """Cache a file for read-before-edit tracking."""
        try:
            content = path.read_text()
            self._file_cache[path] = content
        except Exception:
            pass

    def validate_edit(self, path: Path) -> tuple[bool, str]:
        """Validate that file can be edited (was read first)."""
        if path not in self._file_cache:
            return False, f"File {path} must be read before editing"
        return True, ""

    def track_cost(self, **kwargs) -> None:
        """Track API costs (placeholder)."""
        pass
