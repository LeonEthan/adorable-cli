"""Dynamic context assembly with priority-based truncation.

Claude Code's context assembly:
- Priority-based truncation preserves most important context
- Hierarchical CLAUDE.md loading with override semantics
- Model-specific adaptations (different context windows)
- Parallel fetch of context components
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

from adorable_cli.context.normalizer import (
    NormalizerConfig,
    SizeCalculator,
    normalize_to_size,
)


class PriorityLevel(Enum):
    """Priority levels for context items.

    Items are included in order of priority until size limit reached.
    """

    CRITICAL = 1  # Never truncated (system instructions, active tool calls)
    HIGH = 2  # High priority (current file context, recent messages)
    MEDIUM = 3  # Medium priority (relevant files, tool descriptions)
    LOW = 4  # Lower priority (conversation history)
    SUMMARIZE = 5  # Summarize if needed (old messages)
    DROP = 6  # Drop first if needed (least relevant)


@dataclass
class ContextItem:
    """A single item in the context assembly."""

    content: Any
    priority: PriorityLevel
    source: str  # e.g., "system", "user", "tool", "claude_md"
    estimated_tokens: int = 0
    can_summarize: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.estimated_tokens == 0:
            self.estimated_tokens = self._estimate_tokens()

    def _estimate_tokens(self) -> int:
        """Rough token estimation."""
        if isinstance(self.content, str):
            return len(self.content) // 4
        elif isinstance(self.content, (list, tuple)):
            return len(str(self.content)) // 4
        elif isinstance(self.content, dict):
            return len(str(self.content)) // 4
        return 100  # Default estimate


@dataclass
class AssemblyResult:
    """Result of context assembly."""

    items: list[ContextItem]
    total_tokens: int
    truncated: bool
    summary: str


@dataclass
class ClaudeMdConfig:
    """Configuration for CLAUDE.md loading."""

    filenames: list[str] = field(default_factory=lambda: [
        "CLAUDE.md",
        ".claude/CLAUDE.md",
        ".claude.md",
    ])
    max_size_bytes: int = 50_000
    override_local: bool = True  # Local CLAUDE.md overrides parent


class ContextAssembler:
    """Assembles context with priority-based truncation.

    Implements Claude Code's dynamic context assembly:
    1. Collect context items from various sources
    2. Sort by priority
    3. Include items until token budget exhausted
    4. Summarize lower priority items if needed

    Example:
        assembler = ContextAssembler(max_tokens=200_000)

        # Add items with priorities
        assembler.add_item(system_prompt, PriorityLevel.CRITICAL, "system")
        assembler.add_item(current_file, PriorityLevel.HIGH, "file")
        assembler.add_item(old_messages, PriorityLevel.SUMMARIZE, "history")

        # Assemble context
        result = assembler.assemble()
    """

    # Default token limits by model
    MODEL_LIMITS: dict[str, int] = {
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "claude-3-5-sonnet": 200_000,
        "claude-3-opus": 200_000,
        "claude-3-haiku": 200_000,
    }

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        model_id: Optional[str] = None,
        normalizer_config: Optional[NormalizerConfig] = None,
    ):
        self.max_tokens = max_tokens or self._get_model_limit(model_id)
        self.reserved_tokens = min(4_000, self.max_tokens // 4)  # Reserve for response generation
        self.available_tokens = self.max_tokens - self.reserved_tokens

        self.normalizer_config = normalizer_config or NormalizerConfig(
            max_bytes=self.available_tokens * 4,  # Approximate bytes per token
        )
        self.size_calculator = SizeCalculator()

        self._items: list[ContextItem] = []
        self._claude_md_config = ClaudeMdConfig()

    def _get_model_limit(self, model_id: Optional[str]) -> int:
        """Get token limit for a model."""
        if not model_id:
            return 128_000  # Default

        model_lower = model_id.lower()
        for key, limit in self.MODEL_LIMITS.items():
            if key in model_lower:
                return limit

        return 128_000  # Conservative default

    def add_item(
        self,
        content: Any,
        priority: PriorityLevel,
        source: str,
        can_summarize: bool = False,
        metadata: Optional[dict] = None,
    ) -> "ContextAssembler":
        """Add a context item."""
        item = ContextItem(
            content=content,
            priority=priority,
            source=source,
            can_summarize=can_summarize,
            metadata=metadata or {},
        )
        self._items.append(item)
        return self

    def add_system_prompt(self, prompt: str) -> "ContextAssembler":
        """Add system prompt (CRITICAL priority)."""
        return self.add_item(prompt, PriorityLevel.CRITICAL, "system")

    def add_claude_md(self, content: str, path: Path) -> "ContextAssembler":
        """Add CLAUDE.md content (HIGH priority)."""
        return self.add_item(
            content,
            PriorityLevel.HIGH,
            "claude_md",
            metadata={"path": str(path)},
        )

    def add_user_message(self, message: str) -> "ContextAssembler":
        """Add user message (HIGH priority)."""
        return self.add_item(message, PriorityLevel.HIGH, "user")

    def add_assistant_message(self, message: str) -> "ContextAssembler":
        """Add assistant message (HIGH priority)."""
        return self.add_item(message, PriorityLevel.HIGH, "assistant")

    def add_tool_result(
        self, result: Any, tool_name: str, can_summarize: bool = True
    ) -> "ContextAssembler":
        """Add tool result (MEDIUM priority)."""
        return self.add_item(
            result,
            PriorityLevel.MEDIUM,
            "tool_result",
            can_summarize=can_summarize,
            metadata={"tool_name": tool_name},
        )

    def add_conversation_history(
        self, messages: list[dict], can_summarize: bool = True
    ) -> "ContextAssembler":
        """Add conversation history (LOW priority)."""
        return self.add_item(
            messages,
            PriorityLevel.LOW,
            "history",
            can_summarize=can_summarize,
        )

    def assemble(self) -> AssemblyResult:
        """Assemble context with priority-based truncation.

        1. Sort items by priority
        2. Include items until token budget exhausted
        3. Summarize lower priority items if needed
        4. Return assembled context
        """
        # Sort by priority (lower number = higher priority)
        sorted_items = sorted(self._items, key=lambda x: x.priority.value)

        included: list[ContextItem] = []
        total_tokens = 0
        truncated = False

        for item in sorted_items:
            # Check if we can fit this item
            if total_tokens + item.estimated_tokens <= self.available_tokens:
                included.append(item)
                total_tokens += item.estimated_tokens
            else:
                # Can't fit - try to summarize if allowed
                if item.can_summarize:
                    summarized = self._summarize_item(item)
                    if summarized and total_tokens + summarized.estimated_tokens <= self.available_tokens:
                        included.append(summarized)
                        total_tokens += summarized.estimated_tokens
                        truncated = True
                else:
                    truncated = True

        # Generate summary
        summary_parts = [
            f"Assembled {len(included)} items",
            f"Total tokens: {total_tokens}/{self.available_tokens}",
        ]
        if truncated:
            summary_parts.append("Some items were truncated or summarized")

        return AssemblyResult(
            items=included,
            total_tokens=total_tokens,
            truncated=truncated,
            summary="; ".join(summary_parts),
        )

    def _summarize_item(self, item: ContextItem) -> Optional[ContextItem]:
        """Summarize a context item to reduce size."""
        if isinstance(item.content, list):
            # For lists (like message history), keep first and last few
            if len(item.content) > 4:
                summary_content = [
                    item.content[0],
                    f"... ({len(item.content) - 2} items summarized) ...",
                    item.content[-1],
                ]
                return ContextItem(
                    content=summary_content,
                    priority=item.priority,
                    source=item.source,
                    metadata={**item.metadata, "summarized": True},
                )

        elif isinstance(item.content, str):
            # For strings, truncate
            if len(item.content) > 1000:
                truncated = item.content[:500] + "\n... [content truncated] ...\n" + item.content[-500:]
                return ContextItem(
                    content=truncated,
                    priority=item.priority,
                    source=item.source,
                    metadata={**item.metadata, "truncated": True},
                )

        elif isinstance(item.content, dict):
            # For dicts, normalize
            normalized = normalize_to_size(
                item.content,
                max_bytes=2000,
                config=self.normalizer_config,
                size_calculator=self.size_calculator,
            )
            return ContextItem(
                content=normalized,
                priority=item.priority,
                source=item.source,
                metadata={**item.metadata, "normalized": True},
            )

        return None

    def to_messages(self) -> list[dict[str, Any]]:
        """Assemble and convert to message format for LLM API."""
        result = self.assemble()

        messages: list[dict[str, Any]] = []
        for item in result.items:
            if item.source == "system":
                messages.append({"role": "system", "content": str(item.content)})
            elif item.source == "user":
                messages.append({"role": "user", "content": str(item.content)})
            elif item.source == "assistant":
                messages.append({"role": "assistant", "content": str(item.content)})
            elif item.source == "history" and isinstance(item.content, list):
                # Expand history items
                for msg in item.content:
                    if isinstance(msg, dict) and "role" in msg:
                        messages.append(msg)
            else:
                # Add as system message with source note
                messages.append({
                    "role": "system",
                    "content": f"[{item.source}] {str(item.content)[:5000]}",
                })

        return messages

    def clear(self) -> "ContextAssembler":
        """Clear all items."""
        self._items = []
        return self


class ClaudeMdLoader:
    """Load CLAUDE.md files with hierarchical override semantics."""

    def __init__(self, config: Optional[ClaudeMdConfig] = None):
        self.config = config or ClaudeMdConfig()

    def load(self, start_path: Path) -> dict[Path, str]:
        """Load CLAUDE.md files from directory hierarchy.

        Walks up the directory tree from start_path, loading CLAUDE.md
        files. Closer files override parent files.

        Returns:
            Dict mapping file paths to their content
        """
        results: dict[Path, str] = {}

        current = start_path.resolve()
        if current.is_file():
            current = current.parent

        # Walk up the directory tree
        while True:
            found_local = False
            for filename in self.config.filenames:
                md_path = current / filename
                if md_path.exists() and md_path.is_file():
                    content = self._load_file(md_path)
                    if content:
                        results[md_path] = content
                        found_local = True

            if found_local and self.config.override_local:
                break

            # Stop at root
            if current == current.parent:
                break
            current = current.parent

        return results

    def _load_file(self, path: Path) -> Optional[str]:
        """Load and validate a CLAUDE.md file."""
        try:
            content = path.read_text(encoding="utf-8")
            if len(content.encode()) > self.config.max_size_bytes:
                # Truncate if too large
                content = content[: self.config.max_size_bytes] + "\n... [truncated]"
            return content
        except (IOError, OSError, UnicodeDecodeError):
            return None

    def load_merged(self, start_path: Path) -> str:
        """Load and merge CLAUDE.md files.

        Files closer to start_path take precedence.
        """
        files = self.load(start_path)

        if not files:
            return ""

        if self.config.override_local:
            # Use only the closest file (deepest in the tree)
            closest = max(files.keys(), key=lambda p: len(p.parts))
            return files[closest]
        else:
            # Merge all files with markers
            parts = []
            for path, content in sorted(files.items(), key=lambda x: len(x[0].parts)):
                parts.append(f"<!-- From {path} -->")
                parts.append(content)
            return "\n\n".join(parts)


# Convenience functions

def build_context_for_turn(
    user_input: str,
    conversation_history: list[dict],
    system_instructions: str,
    working_dir: Path,
    model_id: Optional[str] = None,
    tool_results: Optional[list[Any]] = None,
) -> list[dict[str, Any]]:
    """Build complete context for a turn.

    Convenience function that assembles all context components.
    """
    assembler = ContextAssembler(model_id=model_id)

    # Add system instructions (CRITICAL)
    assembler.add_system_prompt(system_instructions)

    # Load CLAUDE.md if present (HIGH)
    md_loader = ClaudeMdLoader()
    claude_md = md_loader.load_merged(working_dir)
    if claude_md:
        assembler.add_claude_md(claude_md, working_dir)

    # Add conversation history (LOW - can summarize)
    if conversation_history:
        assembler.add_conversation_history(conversation_history, can_summarize=True)

    # Add tool results (MEDIUM - can summarize)
    if tool_results:
        for result in tool_results:
            assembler.add_tool_result(result, tool_name="unknown", can_summarize=True)

    # Add user input (HIGH)
    assembler.add_user_message(user_input)

    return assembler.to_messages()
