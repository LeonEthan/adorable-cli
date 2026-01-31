"""Memory and context compression system.

Claude Code's memory management:
- Session summaries for long-term context
- Compression of tool results when context limit reached
- Working memory with automatic cleanup
"""

from adorable_cli.memory.compression import (
    CompressionManager,
    CompressionResult,
    compress_messages,
    compress_tool_result,
)
from adorable_cli.memory.summarizer import (
    SessionSummarizer,
    SummaryResult,
    create_session_summary,
)
from adorable_cli.memory.working_memory import (
    MemoryItem,
    MemoryPriority,
    WorkingMemory,
)

__all__ = [
    # Compression
    "CompressionManager",
    "CompressionResult",
    "compress_messages",
    "compress_tool_result",
    # Summarizer
    "SessionSummarizer",
    "SummaryResult",
    "create_session_summary",
    # Working Memory
    "WorkingMemory",
    "MemoryItem",
    "MemoryPriority",
]
