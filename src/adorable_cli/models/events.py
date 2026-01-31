"""Streaming event types for the agent loop state machine.

These events represent the output of the "tt" async generator function,
which drives the UI updates while maintaining conversation flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4


@dataclass
class StreamEvent:
    """Base class for all stream events."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    turn_id: Optional[str] = None


@dataclass
class ContentDeltaEvent(StreamEvent):
    """Incremental text content from the LLM.

    Yielded during streaming to update the UI in real-time.
    """

    type: Literal["content_delta"] = "content_delta"
    delta: str = ""
    accumulated: str = ""


@dataclass
class ThinkingDeltaEvent(StreamEvent):
    """Incremental thinking/reasoning content from the LLM.

    For models that support reasoning/thinking tokens.
    """

    type: Literal["thinking_delta"] = "thinking_delta"
    delta: str = ""
    accumulated: str = ""


@dataclass
class ToolUseStartEvent(StreamEvent):
    """Signal that the LLM is starting a tool call.

    The tool name and ID are available, but arguments may be partial.
    """

    type: Literal["tool_use_start"] = "tool_use_start"
    tool_use_id: str = ""
    tool_name: str = ""
    partial_input: str = ""  # Raw JSON string, may be incomplete


@dataclass
class ToolUseDeltaEvent(StreamEvent):
    """Incremental tool argument streaming.

    Allows progressive parsing of tool arguments as they arrive.
    """

    type: Literal["tool_use_delta"] = "tool_use_delta"
    tool_use_id: str = ""
    delta: str = ""
    partial_input: str = ""  # Accumulated raw JSON


@dataclass
class ToolUseCompleteEvent(StreamEvent):
    """Tool call arguments are complete and validated.

    Contains the fully parsed tool input ready for execution.
    """

    type: Literal["tool_use_complete"] = "tool_use_complete"
    tool_use_id: str = ""
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultEvent(StreamEvent):
    """Result from executing a tool.

    Contains the output of tool execution, which may be text,
    structured data, or an error.
    """

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    tool_name: str = ""
    result: Any = None
    is_error: bool = False
    error_message: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class ToolConfirmationEvent(StreamEvent):
    """Request user confirmation before executing a tool.

    The loop pauses and yields this event when a tool requires
    user approval (e.g., destructive shell commands).
    """

    type: Literal["tool_confirmation"] = "tool_confirmation"
    tool_use_id: str = ""
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    is_confirmed: Optional[bool] = None  # Set by UI after user response


@dataclass
class ToolExecutionStartEvent(StreamEvent):
    """Signal that tool execution has started.

    Useful for showing progress indicators in the UI.
    """

    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_use_id: str = ""
    tool_name: str = ""


@dataclass
class ToolExecutionProgressEvent(StreamEvent):
    """Progress update during long-running tool execution.

    For tools that support progress reporting (e.g., file searches).
    """

    type: Literal["tool_execution_progress"] = "tool_execution_progress"
    tool_use_id: str = ""
    tool_name: str = ""
    progress_percent: float = 0.0
    message: str = ""


@dataclass
class MessageCompleteEvent(StreamEvent):
    """Final message from the LLM, including all content.

    Contains the complete assistant response and metadata.
    """

    type: Literal["message_complete"] = "message_complete"
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "stop_sequence"] = "end_turn"
    usage: Optional[dict[str, int]] = None  # {input_tokens, output_tokens}


@dataclass
class TurnCompleteEvent(StreamEvent):
    """Signal that the current turn is complete.

    One turn may include multiple message/tool cycles.
    """

    type: Literal["turn_complete"] = "turn_complete"
    turn_number: int = 0
    total_duration_ms: int = 0


@dataclass
class ErrorEvent(StreamEvent):
    """Error during processing."""

    type: Literal["error"] = "error"
    error_type: str = ""  # e.g., "rate_limit", "context_overflow", "tool_error"
    message: str = ""
    recoverable: bool = True
    retry_after_seconds: Optional[int] = None


@dataclass
class CompactionEvent(StreamEvent):
    """Signal that context compaction is occurring.

    Informs the UI that the conversation is being summarized.
    """

    type: Literal["compaction"] = "compaction"
    original_tokens: int = 0
    compacted_tokens: int = 0
    summary: str = ""


# Union type for all events
AgentEvent = (
    ContentDeltaEvent
    | ThinkingDeltaEvent
    | ToolUseStartEvent
    | ToolUseDeltaEvent
    | ToolUseCompleteEvent
    | ToolResultEvent
    | ToolConfirmationEvent
    | ToolExecutionStartEvent
    | ToolExecutionProgressEvent
    | MessageCompleteEvent
    | TurnCompleteEvent
    | ErrorEvent
    | CompactionEvent
)
