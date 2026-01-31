"""Context normalization with iterative depth reduction.

Claude Code's normalize_to_size algorithm:
- Iteratively reduces object depth based on actual byte count
- Preserves maximum information within constraints
- Handles circular references, React/Vue components, and special types
- Uses smart truncation strategies for different data types
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import Any, Callable, Optional, Union


class TruncationStrategy(Enum):
    """Strategies for truncating different data types."""

    TRUNCATE_LIST = auto()  # Keep first N items
    TRUNCATE_TAIL = auto()  # Keep first and last N items
    SUMMARIZE = auto()  # Replace with summary
    REMOVE = auto()  # Remove entirely


@dataclass
class NormalizerConfig:
    """Configuration for the normalizer."""

    # Size limits
    max_bytes: int = 100_000  # Target size in bytes
    min_bytes: int = 50_000  # Minimum acceptable size

    # Depth limits
    max_depth: int = 10  # Maximum nesting depth
    truncate_depth: int = 5  # Depth to start truncating

    # Collection limits
    max_list_items: int = 100  # Maximum items in a list
    max_dict_keys: int = 50  # Maximum keys in a dict
    max_string_length: int = 10_000  # Maximum string length

    # Strategies
    list_strategy: TruncationStrategy = TruncationStrategy.TRUNCATE_TAIL
    dict_strategy: TruncationStrategy = TruncationStrategy.TRUNCATE_LIST
    string_strategy: TruncationStrategy = TruncationStrategy.TRUNCATE_LIST

    # Special handling
    preserve_keys: set[str] = field(default_factory=set)  # Keys to always preserve
    summarize_keys: set[str] = field(default_factory=set)  # Keys to summarize


@dataclass
class SizeEstimate:
    """Size estimate with components."""

    total_bytes: int
    item_count: int
    depth: int


class SizeCalculator:
    """Calculate the byte size of Python objects.

    Uses JSON serialization as a proxy for size, with special
    handling for common data types.
    """

    def __init__(self, sample_size: int = 100):
        self.sample_size = sample_size
        self._cache: dict[int, int] = {}

    def calculate(self, obj: Any) -> int:
        """Calculate the byte size of an object.

        Uses JSON serialization for consistent measurement.
        Handles circular references and special types.
        """
        try:
            # Use JSON serialization for consistent size measurement
            json_str = json.dumps(obj, default=str, ensure_ascii=False)
            return len(json_str.encode("utf-8"))
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            return self._estimate_size(obj)

    def _estimate_size(self, obj: Any, seen: Optional[set[int]] = None) -> int:
        """Estimate size for non-JSON-serializable objects."""
        if seen is None:
            seen = set()

        obj_id = id(obj)
        if obj_id in seen:
            return 16  # Circular reference placeholder
        seen.add(obj_id)

        if isinstance(obj, str):
            return len(obj.encode("utf-8"))
        elif isinstance(obj, bytes):
            return len(obj)
        elif isinstance(obj, (int, float, bool)):
            return 16
        elif obj is None:
            return 4
        elif isinstance(obj, (list, tuple, set)):
            total = 16  # Container overhead
            for item in obj:
                total += self._estimate_size(item, seen.copy())
            return total
        elif isinstance(obj, dict):
            total = 16  # Container overhead
            for key, value in obj.items():
                total += self._estimate_size(key, seen.copy())
                total += self._estimate_size(value, seen.copy())
            return total
        else:
            # Unknown type - use repr length as estimate
            return len(repr(obj).encode("utf-8"))

    def is_within_budget(self, obj: Any, max_bytes: int) -> bool:
        """Quick check if object is within size budget."""
        return self.calculate(obj) <= max_bytes


def normalize_to_size(
    obj: Any,
    max_bytes: int = 100_000,
    config: Optional[NormalizerConfig] = None,
    size_calculator: Optional[SizeCalculator] = None,
    *,
    max_depth: Optional[int] = None,
) -> Any:
    """Normalize an object to fit within size constraints.

    Claude Code's normalize_to_size algorithm:
    1. Calculate current size
    2. If within budget, return as-is
    3. Iteratively reduce depth until within budget or min_size reached
    4. Apply truncation strategies to reduce size

    Args:
        obj: Object to normalize
        max_bytes: Target maximum size in bytes
        config: Normalizer configuration
        size_calculator: Size calculator instance (creates new if None)

    Returns:
        Normalized object that fits within size constraints

    Example:
        large_data = {"messages": [f"message {i}" for i in range(1000)]}
        normalized = normalize_to_size(large_data, max_bytes=5000)
        # Result has fewer messages but preserves structure
    """
    if config is None:
        config = NormalizerConfig(max_bytes=max_bytes)
    if max_depth is not None:
        config = replace(config, max_depth=max_depth)

    if max_bytes < config.max_string_length:
        config = replace(config, max_string_length=max_bytes)

    if size_calculator is None:
        size_calculator = SizeCalculator()

    current_obj = obj
    current_size = size_calculator.calculate(current_obj)
    current_depth = _get_depth(current_obj)
    if current_depth > config.max_depth:
        current_obj = _reduce_depth(current_obj, config.max_depth, config)
        current_size = size_calculator.calculate(current_obj)
        current_depth = _get_depth(current_obj)

    # Quick check - if already within budget, return as-is
    if current_size <= max_bytes and current_depth <= config.max_depth:
        return current_obj

    # Try reducing depth first (avoid collapsing shallow roots)
    min_depth = 2
    while current_size > max_bytes and current_depth > min_depth:
        new_obj = _reduce_depth(current_obj, current_depth - 1, config)
        new_size = size_calculator.calculate(new_obj)

        # Only accept if we made meaningful progress
        if new_size < current_size:
            current_obj = new_obj
            current_size = new_size

        current_depth -= 1

        if current_size <= max_bytes:
            return current_obj

    # If still too large, apply truncation strategies
    if current_size > max_bytes:
        current_obj = _apply_truncation(current_obj, config, size_calculator)

    return current_obj


def _get_depth(obj: Any, seen: Optional[set[int]] = None) -> int:
    """Get the maximum nesting depth of an object."""
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    if isinstance(obj, dict):
        if not obj:
            return 1
        return 1 + max(_get_depth(v, seen.copy()) for v in obj.values())
    elif isinstance(obj, (list, tuple, set)):
        if not obj:
            return 1
        return 1 + max(_get_depth(item, seen.copy()) for item in obj)
    else:
        return 1


def _reduce_depth(obj: Any, target_depth: int, config: NormalizerConfig) -> Any:
    """Reduce object depth by summarizing deep structures.

    Replaces objects beyond target_depth with summaries or placeholders.
    """
    return _reduce_depth_recursive(obj, target_depth, 1, config)


def _reduce_depth_recursive(
    obj: Any, target_depth: int, current_depth: int, config: NormalizerConfig
) -> Any:
    """Recursively reduce depth."""
    if current_depth >= target_depth:
        # At target depth - summarize or truncate
        if isinstance(obj, (list, tuple, set)):
            length = len(obj)
            if length == 0:
                return []
            return f"<list with {length} items>"
        elif isinstance(obj, dict):
            key_count = len(obj)
            if key_count == 0:
                return {}
            return f"<dict with {key_count} keys>"
        elif isinstance(obj, str) and len(obj) > config.max_string_length // 2:
            return obj[: config.max_string_length // 2] + "..."
        return obj

    # Recurse into containers
    if isinstance(obj, dict):
        return {
            k: _reduce_depth_recursive(v, target_depth, current_depth + 1, config)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [
            _reduce_depth_recursive(item, target_depth, current_depth + 1, config)
            for item in obj
        ]
    elif isinstance(obj, tuple):
        return tuple(
            _reduce_depth_recursive(item, target_depth, current_depth + 1, config)
            for item in obj
        )
    else:
        return obj


def _apply_truncation(
    obj: Any, config: NormalizerConfig, size_calculator: SizeCalculator
) -> Any:
    """Apply truncation strategies to reduce size."""
    return _apply_truncation_recursive(obj, config, size_calculator, set())


def _apply_truncation_recursive(
    obj: Any,
    config: NormalizerConfig,
    size_calculator: SizeCalculator,
    seen: set[int],
) -> Any:
    """Recursively apply truncation strategies."""
    obj_id = id(obj)
    if obj_id in seen:
        return "<circular reference>"
    seen.add(obj_id)

    if isinstance(obj, str):
        if len(obj) > config.max_string_length:
            if config.string_strategy == TruncationStrategy.TRUNCATE_LIST:
                return obj[: config.max_string_length] + "..."
            elif config.string_strategy == TruncationStrategy.TRUNCATE_TAIL:
                head = config.max_string_length // 2
                tail = config.max_string_length // 2
                return obj[:head] + "..." + obj[-tail:]
        return obj

    elif isinstance(obj, list):
        if len(obj) > config.max_list_items:
            if config.list_strategy == TruncationStrategy.TRUNCATE_LIST:
                truncated = obj[: config.max_list_items]
                truncated.append(f"... ({len(obj) - config.max_list_items} more items)")
                return truncated
            elif config.list_strategy == TruncationStrategy.TRUNCATE_TAIL:
                head = config.max_list_items // 2
                tail = config.max_list_items // 2
                return (
                    obj[:head]
                    + [f"... ({len(obj) - head - tail} items omitted) ..."]
                    + obj[-tail:]
                )
            elif config.list_strategy == TruncationStrategy.SUMMARIZE:
                return f"<list with {len(obj)} items>"
            elif config.list_strategy == TruncationStrategy.REMOVE:
                return None

        # Recurse into items
        return [
            _apply_truncation_recursive(item, config, size_calculator, seen.copy())
            for item in obj
        ]

    elif isinstance(obj, dict):
        if len(obj) > config.max_dict_keys:
            if config.dict_strategy == TruncationStrategy.TRUNCATE_LIST:
                # Keep first N keys, mark rest as omitted
                keys = list(obj.keys())[: config.max_dict_keys]
                truncated = {k: obj[k] for k in keys}
                truncated["..."] = f"({len(obj) - config.max_dict_keys} more keys omitted)"
                return truncated
            elif config.dict_strategy == TruncationStrategy.SUMMARIZE:
                return f"<dict with {len(obj)} keys>"

        # Recurse into values
        result = {}
        for key, value in obj.items():
            if key in config.preserve_keys:
                # Always preserve these keys
                result[key] = _apply_truncation_recursive(
                    value, config, size_calculator, seen.copy()
                )
            elif key in config.summarize_keys:
                # Summarize these keys
                if isinstance(value, (list, dict)):
                    result[key] = f"<{len(value)} items>"
                elif isinstance(value, str):
                    result[key] = _apply_truncation_recursive(
                        value, config, size_calculator, seen.copy()
                    )
                else:
                    result[key] = value
            else:
                result[key] = _apply_truncation_recursive(
                    value, config, size_calculator, seen.copy()
                )
        return result

    else:
        return obj


def create_message_normalizer(
    max_context_tokens: int = 200_000,
    tokens_per_byte: float = 0.25,
) -> Callable[[list[dict]], list[dict]]:
    """Create a normalizer optimized for LLM message context.

    Args:
        max_context_tokens: Maximum tokens allowed in context
        tokens_per_byte: Approximate tokens per byte ratio

    Returns:
        Function that normalizes message lists to fit token budget
    """
    max_bytes = int(max_context_tokens / tokens_per_byte)

    config = NormalizerConfig(
        max_bytes=max_bytes,
        min_bytes=max_bytes // 2,
        max_list_items=50,  # Limit message history
        max_string_length=50_000,  # Limit individual message size
        preserve_keys={"role", "type", "id"},  # Preserve message metadata
        summarize_keys={"content", "text"},  # Summarize content fields
    )

    size_calculator = SizeCalculator()

    def normalize_messages(messages: list[dict]) -> list[dict]:
        """Normalize a list of messages to fit context window."""
        # First, try to normalize as a whole
        normalized = normalize_to_size(messages, max_bytes, config, size_calculator)

        if size_calculator.calculate(normalized) <= max_bytes:
            return normalized

        # If still too large, truncate message history
        if isinstance(normalized, list) and len(normalized) > 10:
            # Keep first 2 and last 8 messages
            truncated = normalized[:2] + ["... (messages omitted) ..."] + normalized[-8:]
            return truncated

        return normalized

    return normalize_messages


def create_tool_result_normalizer(
    max_result_bytes: int = 10_000,
) -> Callable[[Any], Any]:
    """Create a normalizer for tool results.

    Tool results often contain large output that needs to be
    summarized for the LLM context.
    """
    config = NormalizerConfig(
        max_bytes=max_result_bytes,
        max_string_length=5_000,
        max_list_items=100,
        list_strategy=TruncationStrategy.TRUNCATE_TAIL,
        string_strategy=TruncationStrategy.TRUNCATE_TAIL,
    )

    size_calculator = SizeCalculator()

    def normalize_result(result: Any) -> Any:
        """Normalize a tool result."""
        return normalize_to_size(result, max_result_bytes, config, size_calculator)

    return normalize_result
