"""Context management for the agent loop.

Implements Claude Code's smart context management including:
- normalize_to_size: Iterative depth reduction based on byte count
- Priority-based context assembly
- Hierarchical CLAUDE.md loading
"""

from adorable_cli.context.normalizer import (
    normalize_to_size,
    NormalizerConfig,
    SizeCalculator,
    TruncationStrategy,
)
from adorable_cli.context.assembler import (
    ContextAssembler,
    PriorityLevel,
    ContextItem,
    AssemblyResult,
)
from adorable_cli.context.agent_context import AgentContext

__all__ = [
    "normalize_to_size",
    "NormalizerConfig",
    "SizeCalculator",
    "TruncationStrategy",
    "ContextAssembler",
    "PriorityLevel",
    "ContextItem",
    "AssemblyResult",
    "AgentContext",
]
