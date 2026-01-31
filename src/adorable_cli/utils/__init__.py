"""Utility modules for Adorable CLI."""

from adorable_cli.utils.streaming_json import (
    StreamingJSONParser,
    JSONParseError,
    PartialJSONError,
    RecoveryStrategy,
    parse_partial_json,
    extract_complete_objects,
)
from adorable_cli.utils.errors import (
    ToolError,
    format_tool_error,
    categorize_error,
    is_retryable_error,
    FileSafetyError,
    ToolNotFoundError,
    ConfirmationRequiredError,
)
from adorable_cli.utils.backpressure import (
    BackpressureController,
    StreamBackpressureAdapter,
    BackpressureStats,
    EventPriority,
    PrioritizedEvent,
    get_priority_for_event,
)

__all__ = [
    # Streaming JSON
    "StreamingJSONParser",
    "JSONParseError",
    "PartialJSONError",
    "RecoveryStrategy",
    "parse_partial_json",
    "extract_complete_objects",
    # Errors
    "ToolError",
    "format_tool_error",
    "categorize_error",
    "is_retryable_error",
    "FileSafetyError",
    "ToolNotFoundError",
    "ConfirmationRequiredError",
    # Backpressure
    "BackpressureController",
    "StreamBackpressureAdapter",
    "BackpressureStats",
    "EventPriority",
    "PrioritizedEvent",
    "get_priority_for_event",
]
