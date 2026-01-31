"""Three-stage message representation system.

Claude Code uses a three-stage pipeline:
- CliMessage: UI/metadata layer
- APIMessage: API wire format
- StreamAccumulator: Partial results during streaming

This module implements the core message data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4


MessageRole = Literal["system", "user", "assistant", "tool"]
MessageType = Literal["user", "assistant", "attachment", "progress", "error"]


@dataclass
class TextBlock:
    """Plain text content block."""

    type: Literal["text"] = "text"
    text: str = ""
    citations: Optional[list[dict[str, Any]]] = None


@dataclass
class ImageBlock:
    """Image content block (user input)."""

    type: Literal["image"] = "image"
    source: dict[str, Any] = field(default_factory=dict)
    # source contains: type ("base64"), media_type, data


@dataclass
class ToolUseBlock:
    """Tool invocation block (assistant output).

    Represents a request from the assistant to use a tool.
    """

    type: Literal["tool_use"] = "tool_use"
    id: str = ""  # Unique ID for this tool use
    name: str = ""  # Tool name
    input: dict[str, Any] = field(default_factory=dict)  # Parsed arguments
    partial_input: str = ""  # Raw JSON during streaming


@dataclass
class ToolResultBlock:
    """Tool execution result block.

    Contains the output of a tool execution.
    """

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""  # Matches ToolUseBlock.id
    content: str | list[dict[str, Any]] = ""
    is_error: bool = False
    error_message: Optional[str] = None


@dataclass
class ThinkingBlock:
    """Reasoning/thinking content from the model.

    For models that expose their reasoning process.
    """

    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    signature: Optional[str] = None  # For verifiable thinking


@dataclass
class DocumentBlock:
    """Document content (for platforms supporting document input)."""

    type: Literal["document"] = "document"
    source: dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None
    context: Optional[str] = None


# Union type for all content blocks
ContentBlock = TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock | ThinkingBlock | DocumentBlock


@dataclass
class APIMessage:
    """Message format for LLM API communication.

    This is the wire format used when sending/receiving messages
    to/from the LLM API.
    """

    role: MessageRole = "user"
    content: str | list[ContentBlock] = field(default_factory=str)
    # Additional metadata
    name: Optional[str] = None  # For tool messages identifying the tool
    tool_call_id: Optional[str] = None  # Links tool_result to tool_use

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to dictionary format expected by LLM APIs."""
        result: dict[str, Any] = {"role": self.role}

        if isinstance(self.content, str):
            result["content"] = self.content
        else:
            # Convert content blocks to API format
            result["content"] = [
                self._block_to_dict(block) for block in self.content
            ]

        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id

        return result

    @staticmethod
    def _block_to_dict(block: ContentBlock) -> dict[str, Any]:
        """Convert a content block to API dictionary format."""
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        elif isinstance(block, ImageBlock):
            return {"type": "image", "source": block.source}
        elif isinstance(block, ToolUseBlock):
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        elif isinstance(block, ToolResultBlock):
            return {
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
                "content": block.content,
                "is_error": block.is_error,
            }
        elif isinstance(block, ThinkingBlock):
            return {"type": "thinking", "thinking": block.thinking}
        elif isinstance(block, DocumentBlock):
            return {"type": "document", **block.__dict__}
        return {}


@dataclass
class CliMessage:
    """UI-facing message with metadata and display state.

    This is the primary message type used throughout the CLI.
    It wraps APIMessages with UI state, progress tracking, and cost info.
    """

    # Identity
    uuid: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    # Message type
    type: MessageType = "assistant"

    # The underlying API message (for assistant/user messages)
    message: Optional[APIMessage] = None

    # Content blocks for rich display
    content_blocks: list[ContentBlock] = field(default_factory=list)

    # UI state
    is_complete: bool = False
    is_error: bool = False
    error_message: Optional[str] = None

    # Progress tracking (for in-progress tool operations)
    progress: Optional[ProgressState] = None

    # Cost and performance metrics
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    token_usage: Optional[TokenUsage] = None

    # Metadata
    model: Optional[str] = None
    stop_reason: Optional[str] = None

    @classmethod
    def from_user_input(cls, text: str) -> "CliMessage":
        """Create a user message from input text."""
        return cls(
            type="user",
            message=APIMessage(role="user", content=text),
            content_blocks=[TextBlock(text=text)],
            is_complete=True,
        )

    @classmethod
    def from_assistant_response(cls, content: str) -> "CliMessage":
        """Create an assistant message from response text."""
        return cls(
            type="assistant",
            message=APIMessage(role="assistant", content=content),
            content_blocks=[TextBlock(text=content)],
        )

    @classmethod
    def for_tool_progress(cls, tool_name: str, tool_use_id: str) -> "CliMessage":
        """Create a progress message for tool execution."""
        return cls(
            type="progress",
            progress=ProgressState(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                status="running",
            ),
        )

    def append_text(self, text: str) -> None:
        """Append text to the message content (for streaming)."""
        if not self.content_blocks:
            self.content_blocks.append(TextBlock(text=text))
        elif isinstance(self.content_blocks[-1], TextBlock):
            self.content_blocks[-1].text += text
        else:
            self.content_blocks.append(TextBlock(text=text))

        # Update underlying message
        if self.message:
            if isinstance(self.message.content, str):
                self.message.content += text
            else:
                # Convert to blocks if needed
                self.message.content = self.content_blocks

    def add_tool_use(self, tool_use: ToolUseBlock) -> None:
        """Add a tool use block to the message."""
        self.content_blocks.append(tool_use)
        if self.message and isinstance(self.message.content, list):
            self.message.content.append(tool_use)

    def update_tool_input(self, tool_use_id: str, partial_json: str) -> None:
        """Update partial tool input during streaming."""
        for block in self.content_blocks:
            if isinstance(block, ToolUseBlock) and block.id == tool_use_id:
                block.partial_input = partial_json
                break

    def finalize_tool_input(self, tool_use_id: str, parsed_input: dict[str, Any]) -> None:
        """Finalize tool input after streaming is complete."""
        for block in self.content_blocks:
            if isinstance(block, ToolUseBlock) and block.id == tool_use_id:
                block.input = parsed_input
                block.partial_input = ""
                break

    def add_tool_result(self, result: ToolResultBlock) -> None:
        """Add a tool result block."""
        self.content_blocks.append(result)

    def get_text_content(self) -> str:
        """Get concatenated text from all text blocks."""
        texts = []
        for block in self.content_blocks:
            if isinstance(block, TextBlock):
                texts.append(block.text)
            elif isinstance(block, ToolUseBlock):
                texts.append(f"[{block.name}({block.input})]")
            elif isinstance(block, ToolResultBlock):
                if isinstance(block.content, str):
                    texts.append(block.content)
        return "".join(texts)


@dataclass
class ProgressState:
    """Progress tracking for tool execution."""

    tool_use_id: str = ""
    tool_name: str = ""
    status: Literal["running", "complete", "error"] = "running"
    message: str = ""
    percent: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None


@dataclass
class TokenUsage:
    """Token usage statistics."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class StreamAccumulator:
    """Accumulator for partial streaming results.

    Maintains state during streaming and builds up a complete CliMessage.
    This is the "working memory" of the streaming process.
    """

    message_id: str = field(default_factory=lambda: str(uuid4()))
    role: MessageRole = "assistant"

    # Accumulated content
    text_buffer: str = ""
    tool_use_blocks: list[ToolUseBlock] = field(default_factory=list)
    current_tool_use: Optional[ToolUseBlock] = None

    # State machine for streaming
    state: Literal["idle", "message_start", "content", "tool_input", "complete"] = "idle"

    # Metrics
    start_time: datetime = field(default_factory=datetime.now)
    token_count: int = 0

    def append_text(self, delta: str) -> None:
        """Append text delta to the buffer."""
        self.text_buffer += delta
        self.token_count += len(delta) // 4  # Rough estimate

    def start_tool_use(self, tool_name: str, tool_use_id: str) -> None:
        """Start accumulating a new tool use block."""
        self.current_tool_use = ToolUseBlock(
            id=tool_use_id,
            name=tool_name,
            partial_input="",
        )
        self.state = "tool_input"

    def append_tool_input(self, delta: str) -> None:
        """Append to the current tool's partial input."""
        if self.current_tool_use:
            self.current_tool_use.partial_input += delta

    def finalize_tool_input(self, parsed_input: dict[str, Any]) -> None:
        """Finalize the current tool use block."""
        if self.current_tool_use:
            self.current_tool_use.input = parsed_input
            self.current_tool_use.partial_input = ""
            self.tool_use_blocks.append(self.current_tool_use)
            self.current_tool_use = None
            self.state = "content"

    def to_cli_message(self) -> CliMessage:
        """Convert accumulator to a complete CliMessage."""
        content_blocks: list[ContentBlock] = []

        if self.text_buffer:
            content_blocks.append(TextBlock(text=self.text_buffer))

        content_blocks.extend(self.tool_use_blocks)

        return CliMessage(
            uuid=self.message_id,
            type="assistant",
            message=APIMessage(
                role="assistant",
                content=content_blocks if len(content_blocks) > 1 else self.text_buffer,
            ),
            content_blocks=content_blocks,
            is_complete=True,
            duration_ms=int(
                (datetime.now() - self.start_time).total_seconds() * 1000
            ),
        )
