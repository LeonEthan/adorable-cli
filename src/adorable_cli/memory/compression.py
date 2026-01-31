"""Context compression for managing token limits.

Claude Code's compression system:
- Compresses tool results when context limit reached
- Preserves essential information (file paths, errors, key outputs)
- Removes redundant formatting and boilerplate
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CompressionResult:
    """Result of compression operation."""

    original_size: int
    compressed_size: int
    content: Any
    compression_ratio: float = 0.0
    was_compressed: bool = False

    def __post_init__(self):
        if self.original_size > 0:
            self.compression_ratio = 1.0 - (self.compressed_size / self.original_size)


class CompressionManager:
    """Manages compression of context items.

    Compresses tool results and messages when approaching token limits,
    preserving essential information for the LLM.
    """

    # Patterns to remove during compression
    REDUNDANT_PATTERNS = [
        r"\n{3,}",  # Multiple blank lines
        r"[ \t]+\n",  # Trailing whitespace
        r"^\s*#+\s*$",  # Lines with only comment markers
        r"\[.*?\]\s*\[.*?\]",  # Nested brackets (often verbose logging)
    ]

    # Essential patterns to preserve
    ESSENTIAL_PATTERNS = [
        r"Error[:\s]",
        r"Exception[:\s]",
        r"File[:\s]",
        r"Path[:\s]",
        r"http[s]?://",
    ]

    def __init__(
        self,
        compress_threshold: int = 50,  # Compress after N tool results
        target_size_ratio: float = 0.5,  # Target 50% of original
    ):
        self.compress_threshold = compress_threshold
        self.target_size_ratio = target_size_ratio
        self._compression_count = 0

    def should_compress(self, item_count: int) -> bool:
        """Check if compression should be triggered."""
        return item_count >= self.compress_threshold

    def compress_tool_result(
        self,
        result: Any,
        tool_name: Optional[str] = None,
        aggressive: bool = False,
    ) -> CompressionResult:
        """Compress a tool result while preserving essential info.

        Args:
            result: Tool result to compress
            tool_name: Name of the tool (for context-aware compression)
            aggressive: If True, apply more aggressive compression

        Returns:
            CompressionResult with compressed content
        """
        original_str = str(result)
        original_size = len(original_str)

        if original_size < 500:  # Don't compress small results
            return CompressionResult(
                original_size=original_size,
                compressed_size=original_size,
                content=result,
                was_compressed=False,
            )

        # Apply compression strategies
        compressed = original_str

        # Strategy 1: Remove redundant patterns
        for pattern in self.REDUNDANT_PATTERNS:
            compressed = re.sub(pattern, "\n\n" if "\\n" in pattern else "", compressed)

        # Strategy 2: Truncate long lines
        lines = compressed.split("\n")
        truncated_lines = []
        for line in lines:
            if len(line) > 200 and not self._is_essential(line):
                line = line[:200] + "..."
            truncated_lines.append(line)
        compressed = "\n".join(truncated_lines)

        # Strategy 3: Limit total lines
        max_lines = 50 if not aggressive else 20
        if len(truncated_lines) > max_lines:
            # Keep first 1/4, middle indicator, last 3/4
            quarter = max_lines // 4
            compressed = "\n".join(
                truncated_lines[:quarter]
                + [f"... ({len(truncated_lines) - max_lines} lines omitted) ..."]
                + truncated_lines[-(max_lines - quarter):]
            )

        # Strategy 4: Tool-specific compression
        if tool_name:
            compressed = self._tool_specific_compression(compressed, tool_name)

        compressed_size = len(compressed)

        return CompressionResult(
            original_size=original_size,
            compressed_size=compressed_size,
            content=compressed,
            was_compressed=True,
        )

    def _is_essential(self, line: str) -> bool:
        """Check if a line contains essential information."""
        for pattern in self.ESSENTIAL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    def _tool_specific_compression(
        self, content: str, tool_name: str
    ) -> str:
        """Apply tool-specific compression rules."""
        tool_name_lower = tool_name.lower()

        if "shell" in tool_name_lower or "bash" in tool_name_lower:
            # Keep stdout/stderr but compress repetitive output
            return self._compress_shell_output(content)

        if "file" in tool_name_lower:
            # Keep file paths and key content
            return self._compress_file_output(content)

        if "search" in tool_name_lower or "grep" in tool_name_lower:
            # Keep search results but limit matches
            return self._compress_search_output(content)

        return content

    def _compress_shell_output(self, content: str) -> str:
        """Compress shell command output."""
        lines = content.split("\n")

        # Remove progress bars and spinners
        filtered = [
            line for line in lines
            if not self._is_progress_line(line)
        ]

        # If still long, truncate
        if len(filtered) > 50:
            return "\n".join(
                filtered[:20]
                + [f"... ({len(filtered) - 40} lines omitted) ..."]
                + filtered[-20:]
            )

        return "\n".join(filtered)

    def _compress_file_output(self, content: str) -> str:
        """Compress file listing output."""
        lines = content.split("\n")

        # Group files by directory, show counts
        dirs: dict[str, list[str]] = {}
        for line in lines:
            if "/" in line:
                dir_path = line.rsplit("/", 1)[0]
                if dir_path not in dirs:
                    dirs[dir_path] = []
                dirs[dir_path].append(line)

        # If many files in same directory, summarize
        if len(lines) > 30 and dirs:
            summary_lines = []
            for dir_path, files in dirs.items():
                if len(files) > 5:
                    summary_lines.append(f"{dir_path}/: {len(files)} files")
                else:
                    summary_lines.extend(files)
            return "\n".join(summary_lines)

        return content

    def _compress_search_output(self, content: str) -> str:
        """Compress search output."""
        lines = content.split("\n")

        # Limit matches per file
        file_matches: dict[str, list[str]] = {}
        for line in lines:
            file_path = line.split(":")[0] if ":" in line else "unknown"
            if file_path not in file_matches:
                file_matches[file_path] = []
            file_matches[file_path].append(line)

        # Summarize if many matches
        compressed_lines = []
        for file_path, matches in file_matches.items():
            if len(matches) > 5:
                compressed_lines.append(f"{file_path}: {len(matches)} matches")
                compressed_lines.extend(matches[:3])
                compressed_lines.append("...")
            else:
                compressed_lines.extend(matches)

        return "\n".join(compressed_lines[:50])  # Limit total lines

    def _is_progress_line(self, line: str) -> bool:
        """Check if line is a progress indicator."""
        progress_patterns = [
            r"[#\-\\/|]+\s*\d+%",  # Progress bars
            r"\d+/\d+\s+\[",  # Count progress
            r"\.+\s*\d+%",  # Dots with percentage
        ]
        for pattern in progress_patterns:
            if re.search(pattern, line):
                return True
        return False


def compress_tool_result(
    result: Any,
    max_length: int = 2000,
    preserve_errors: bool = True,
) -> str:
    """Compress a tool result to fit within max_length.

    Convenience function for one-off compression.

    Args:
        result: Tool result to compress
        max_length: Maximum desired length
        preserve_errors: If True, always keep error messages

    Returns:
        Compressed string representation
    """
    result_str = str(result)

    if len(result_str) <= max_length:
        return result_str

    # If it's an error and we need to preserve it
    if preserve_errors and ("error" in result_str.lower() or "exception" in result_str.lower()):
        # Keep the error but compress context
        lines = result_str.split("\n")
        error_lines = [
            line for line in lines
            if "error" in line.lower() or "exception" in line.lower() or "traceback" in line.lower()
        ]
        return "\n".join(error_lines[:20])

    # General compression
    manager = CompressionManager()
    compression_result = manager.compress_tool_result(result, aggressive=True)

    if len(compression_result.content) <= max_length:
        return compression_result.content

    # Still too long - truncate with indicator
    truncated = compression_result.content[:max_length - 50]
    return truncated + "\n... [content truncated]"


def compress_messages(
    messages: list[dict[str, Any]],
    target_count: int = 10,
) -> list[dict[str, Any]]:
    """Compress message history to target count.

    Strategy:
    - Keep first message (system prompt)
    - Keep last N messages (recent context)
    - Summarize middle messages

    Args:
        messages: List of messages
        target_count: Target number of messages

    Returns:
        Compressed message list
    """
    if len(messages) <= target_count:
        return messages

    # Always keep system message
    system_messages = [m for m in messages if m.get("role") == "system"]
    other_messages = [m for m in messages if m.get("role") != "system"]

    # Keep first user message for context
    first_user = None
    for m in other_messages:
        if m.get("role") == "user":
            first_user = m
            break

    # Keep last N-2 messages for recent context
    keep_count = target_count - len(system_messages) - (1 if first_user else 0)
    recent_messages = other_messages[-keep_count:]

    # Middle messages get summarized
    middle_start = 1 if first_user else 0
    middle_end = len(other_messages) - keep_count
    middle_messages = other_messages[middle_start:middle_end]

    result = system_messages.copy()

    if first_user:
        result.append(first_user)

    if middle_messages:
        result.append({
            "role": "system",
            "content": f"[Earlier conversation: {len(middle_messages)} messages summarized]",
        })

    result.extend(recent_messages)

    return result
