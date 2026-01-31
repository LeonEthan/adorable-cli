"""Core async generator agent loop (the "tt" function).

This module implements Claude Code's six-phase orchestration pattern:
1. Turn Initialization - context window pressure checks
2. Dynamic System Prompt Assembly - parallel fetch of tools, git state, etc.
3. LLM Stream Initialization - streaming API call setup
4. Stream Event Processing - real-time state machine
5. Tool Execution Orchestration - parallel batch processing
6. Recursive Turn Management - tail-recursive continuation

The AgentLoop is an async generator that yields StreamEvent objects,
allowing the UI to update in real-time while maintaining conversation flow.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Optional, cast

from adorable_cli.context.agent_context import AgentContext
from adorable_cli.core.anr_detector import AsyncANRDetector, ANREvent
from adorable_cli.models.events import (
    AgentEvent,
    CompactionEvent,
    ContentDeltaEvent,
    ErrorEvent,
    MessageCompleteEvent,
    ThinkingDeltaEvent,
    ToolConfirmationEvent,
    ToolExecutionProgressEvent,
    ToolExecutionStartEvent,
    ToolResultEvent,
    ToolUseCompleteEvent,
    ToolUseDeltaEvent,
    ToolUseStartEvent,
    TurnCompleteEvent,
)
from adorable_cli.models.messages import (
    APIMessage,
    CliMessage,
    StreamAccumulator,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from adorable_cli.utils.backpressure import (
    BackpressureController,
    EventPriority,
    get_priority_for_event,
)
from adorable_cli.utils.streaming_json import (
    IncrementalJSONParser,
)


@dataclass
class LoopConfig:
    """Configuration for the agent loop."""

    # Model configuration
    model_id: str = "gpt-4o"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    # Context management
    max_context_tokens: int = 200_000
    compaction_threshold: float = 0.85

    # Tool execution
    max_parallel_read_tools: int = 10
    enable_confirmations: bool = True

    # Turn management
    max_turns: int = 100
    max_tool_calls_per_turn: int = 32

    # Safety
    forbidden_commands: list[str] = field(
        default_factory=lambda: ["rm -rf /", "sudo", "chmod -R 000 /"]
    )

    # ANR detection
    enable_anr_detection: bool = True
    anr_threshold_ms: float = 5000  # Claude Code default

    # Backpressure control
    enable_backpressure: bool = True
    backpressure_buffer_size: int = 1000
    backpressure_drop_threshold: float = 0.9
    backpressure_pause_threshold: float = 0.8
    backpressure_resume_threshold: float = 0.5


@dataclass
class TurnState:
    """State for a single turn of the conversation.

    Tracks accumulated content, tool calls, and execution progress.
    """

    turn_number: int = 0
    user_input: str = ""

    # Accumulator for streaming content
    accumulator: StreamAccumulator = field(default_factory=StreamAccumulator)

    # Pending tool calls awaiting execution
    pending_tool_calls: list[ToolUseBlock] = field(default_factory=list)

    # Completed tool results for this turn
    tool_results: list[ToolResultBlock] = field(default_factory=list)

    # Metrics
    start_time: datetime = field(default_factory=datetime.now)
    tool_call_count: int = 0

    def elapsed_ms(self) -> int:
        """Get elapsed time in milliseconds."""
        return int((datetime.now() - self.start_time).total_seconds() * 1000)


class AgentLoop:
    """Six-phase async generator agent loop.

    Similar to Claude Code's "tt" function, this class orchestrates
    the entire conversation flow through an async generator pattern.

    Usage:
        loop = AgentLoop(agent, context, config)
        async for event in loop.run(user_input):
            # Update UI based on event type
            if isinstance(event, ContentDeltaEvent):
                update_text_display(event.delta)
            elif isinstance(event, ToolConfirmationEvent):
                # Pause for user confirmation
                event.is_confirmed = await show_confirmation_dialog(event)
    """

    def __init__(
        self,
        agent: Any,
        context: AgentContext,
        config: Optional[LoopConfig] = None,
        tool_executor: Optional[Any] = None,
    ):
        self.agent = agent
        self.context = context
        self.config = config or LoopConfig()
        self.tool_executor = tool_executor

        # State
        self._turn_state: Optional[TurnState] = None
        self._json_parser: Optional[IncrementalJSONParser] = None

        # Streaming state machine
        self._current_tool_use: Optional[ToolUseBlock] = None

        # ANR detection
        self._anr_detector: Optional[AsyncANRDetector] = None
        if self.config.enable_anr_detection:
            self._anr_detector = AsyncANRDetector(
                threshold_ms=self.config.anr_threshold_ms,
                on_anr=self._on_anr_detected,
            )

        # Backpressure controller
        self._backpressure: Optional[BackpressureController] = None
        if self.config.enable_backpressure:
            self._backpressure = BackpressureController(
                buffer_size=self.config.backpressure_buffer_size,
                drop_threshold=self.config.backpressure_drop_threshold,
                pause_threshold=self.config.backpressure_pause_threshold,
                resume_threshold=self.config.backpressure_resume_threshold,
            )

    # ========================================================================
    # Phase 1: Turn Initialization
    # ========================================================================

    async def _phase1_turn_init(self, user_input: str) -> TurnState:
        """Initialize a new turn with context window checks."""
        self.context.turn_count += 1

        # Check context window pressure
        if self.context.window.should_compact():
            # Yield compaction event before proceeding
            await self._yield_compaction_notice()

        # Create new turn state
        turn = TurnState(
            turn_number=self.context.turn_count,
            user_input=user_input,
            accumulator=StreamAccumulator(),
        )

        # Add user message to history
        user_msg = CliMessage.from_user_input(user_input)
        self.context.history.add_message(user_msg)

        self._turn_state = turn
        return turn

    async def _yield_compaction_notice(self) -> None:
        """Notify that context compaction is occurring."""
        # This would be yielded to the caller in a real implementation
        pass

    # ========================================================================
    # Phase 2: Dynamic System Prompt Assembly
    # ========================================================================

    async def _phase2_assemble_prompt(self) -> list[APIMessage]:
        """Assemble the full prompt with dynamic context.

        This is done in parallel for performance:
        - Fetch current directory structure
        - Load CLAUDE.md if present
        - Get git state
        - Build tool descriptions
        """
        # Build context messages (system + history)
        messages = self.context.build_context_messages()

        # Add user input as the final message
        messages.append(APIMessage(role="user", content=self._turn_state.user_input))

        return messages

    # ========================================================================
    # Phase 3: LLM Stream Initialization
    # ========================================================================

    async def _phase3_init_stream(
        self, messages: list[APIMessage]
    ) -> AsyncGenerator[Any, None]:
        """Initialize the LLM streaming API call."""
        # Convert messages to API format
        api_messages = [msg.to_api_dict() for msg in messages]

        # Start streaming
        stream = self.agent.arun(
            api_messages[-1].get("content", ""),  # User input
            stream=True,
            stream_intermediate_steps=True,
        )

        if hasattr(stream, "__aiter__"):
            async for event in stream:
                yield event
        else:
            for event in stream:
                yield event

    # ========================================================================
    # Phase 4: Stream Event Processing
    # ========================================================================

    async def _phase4_process_stream(
        self, stream: AsyncGenerator[Any, None]
    ) -> AsyncGenerator[AgentEvent, None]:
        """Process the LLM stream with state machine.

        Handles:
        - Text deltas
        - Tool use start/complete
        - Tool argument streaming
        - Thinking/reasoning content
        """
        accumulator = self._turn_state.accumulator
        self._json_parser = None

        async for event in stream:
            event_type = getattr(event, "event", "")

            # Handle content streaming
            if event_type in ("RunContent", "TeamRunContent"):
                content = getattr(event, "content", "")
                if content:
                    accumulator.append_text(content)
                    yield ContentDeltaEvent(
                        delta=content,
                        accumulated=accumulator.text_buffer,
                        turn_id=str(self._turn_state.turn_number),
                    )

            # Handle tool calls starting
            elif event_type in ("ToolCallStarted", "RunToolCallStarted"):
                tools = getattr(event, "tools", []) or getattr(
                    event, "tools_requiring_confirmation", []
                )
                for tool in tools:
                    tool_name = getattr(tool, "tool_name", None) or getattr(
                        tool, "name", "unknown"
                    )
                    tool_use_id = str(uuid.uuid4())

                    tool_block = ToolUseBlock(
                        id=tool_use_id,
                        name=tool_name,
                        partial_input="",
                    )

                    accumulator.start_tool_use(tool_name, tool_use_id)
                    self._current_tool_use = tool_block
                    if self._json_parser is None:
                        self._json_parser = IncrementalJSONParser()
                    self._json_parser.start_tool(tool_use_id)

                    yield ToolUseStartEvent(
                        tool_use_id=tool_use_id,
                        tool_name=tool_name,
                        partial_input="",
                        turn_id=str(self._turn_state.turn_number),
                    )

            # Handle thinking/reasoning content
            elif event_type == "Thinking":
                thinking = getattr(event, "thinking", "")
                if thinking:
                    yield ThinkingDeltaEvent(
                        delta=thinking,
                        accumulated=thinking,
                        turn_id=str(self._turn_state.turn_number),
                    )

            # Handle completion
            elif event_type in ("RunCompleted", "TeamRunCompleted"):
                content = getattr(event, "content", "")
                metrics = getattr(event, "metrics", None)

                # Finalize any pending tool
                if self._current_tool_use and self._json_parser:
                    tool_use_id = self._current_tool_use.id
                    parsed = self._json_parser.try_parse(tool_use_id)
                    if parsed is None:
                        # Try with recovery
                        parsed = self._json_parser.finalize(tool_use_id)
                    if parsed:
                        self._current_tool_use.input = parsed
                        accumulator.finalize_tool_input(
                            self._current_tool_use.id, parsed
                        )
                        yield ToolUseCompleteEvent(
                            tool_use_id=self._current_tool_use.id,
                            tool_name=self._current_tool_use.name,
                            tool_input=parsed,
                            turn_id=str(self._turn_state.turn_number),
                        )

                usage = None
                if metrics:
                    usage = {
                        "input_tokens": getattr(metrics, "input_tokens", 0),
                        "output_tokens": getattr(metrics, "output_tokens", 0),
                    }

                yield MessageCompleteEvent(
                    content=content,
                    stop_reason="end_turn",
                    usage=usage,
                    turn_id=str(self._turn_state.turn_number),
                )

    # ========================================================================
    # Phase 5: Tool Execution Orchestration
    # ========================================================================

    async def _phase5_execute_tools(
        self, tool_calls: list[ToolUseBlock]
    ) -> AsyncGenerator[AgentEvent, None]:
        """Execute tools with parallel read-only and serial write semantics.

        Categorizes tools by side effects and executes accordingly:
        - Read-only tools: parallel execution (max 10)
        - Write tools: sequential execution
        - Dangerous tools: user confirmation required
        """
        if not tool_calls:
            return

        # Categorize tool calls
        read_only_calls: list[ToolUseBlock] = []
        write_calls: list[ToolUseBlock] = []
        dangerous_calls: list[ToolUseBlock] = []

        for tool in tool_calls:
            tool_name = tool.name
            if self.context.tools.is_dangerous(tool_name):
                dangerous_calls.append(tool)
            elif self.context.tools.is_read_only(tool_name):
                read_only_calls.append(tool)
            else:
                write_calls.append(tool)

        # Process dangerous calls with confirmation
        for tool in dangerous_calls:
            if self.config.enable_confirmations:
                confirm_event = ToolConfirmationEvent(
                    tool_use_id=tool.id,
                    tool_name=tool.name,
                    tool_input=tool.input,
                    reason="Potentially destructive operation",
                    turn_id=str(self._turn_state.turn_number),
                )
                yield confirm_event

                # Wait for confirmation (UI sets is_confirmed)
                if not confirm_event.is_confirmed:
                    yield ToolResultEvent(
                        tool_use_id=tool.id,
                        tool_name=tool.name,
                        result="",
                        is_error=True,
                        error_message="User declined to run this tool",
                        turn_id=str(self._turn_state.turn_number),
                    )
                    continue

            # Execute after confirmation
            async for event in self._execute_single_tool(tool):
                yield event

        # Execute read-only tools in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(self.config.max_parallel_read_tools)

        async def execute_with_limit(tool: ToolUseBlock) -> list[AgentEvent]:
            async with semaphore:
                events: list[AgentEvent] = []
                async for event in self._execute_single_tool(tool):
                    events.append(event)
                return events

        # Run all read-only tools concurrently
        if read_only_calls:
            tasks = [execute_with_limit(tool) for tool in read_only_calls]
            results = await asyncio.gather(*tasks)
            for events in results:
                for event in events:
                    yield event

        # Execute write tools sequentially
        for tool in write_calls:
            async for event in self._execute_single_tool(tool):
                yield event

    async def _execute_single_tool(
        self, tool: ToolUseBlock
    ) -> AsyncGenerator[AgentEvent, None]:
        """Execute a single tool and yield progress/result events."""
        tool_use_id = tool.id
        tool_name = tool.name
        tool_input = tool.input

        start_time = datetime.now()

        yield ToolExecutionStartEvent(
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            turn_id=str(self._turn_state.turn_number),
        )

        try:
            # Execute the tool
            result = await self._invoke_tool(tool_name, tool_input)

            execution_time = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            yield ToolResultEvent(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                result=result,
                is_error=False,
                execution_time_ms=execution_time,
                turn_id=str(self._turn_state.turn_number),
            )

        except Exception as e:
            execution_time = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            yield ToolResultEvent(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                result="",
                is_error=True,
                error_message=str(e),
                execution_time_ms=execution_time,
                turn_id=str(self._turn_state.turn_number),
            )

    async def _invoke_tool(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> Any:
        """Invoke a tool by name with the given input."""
        # Check file safety for file operations
        if tool_name in ("read_file", "save_file", "replace_file_chunk"):
            file_path = tool_input.get("file_path") or tool_input.get("path")
            if file_path:
                path = Path(file_path)
                if not path.is_absolute():
                    path = self.context.cwd / path

                if tool_name == "read_file":
                    # Cache file for read-before-edit
                    self.context.cache_file(path)

                elif tool_name in ("save_file", "replace_file_chunk"):
                    # Validate read-before-edit
                    is_valid, error = self.context.validate_edit(path)
                    if not is_valid:
                        raise RuntimeError(f"File safety violation: {error}")

        # Check for forbidden commands in shell operations
        if tool_name == "run_shell_command":
            command = tool_input.get("command", "")
            for forbidden in self.config.forbidden_commands:
                if forbidden in command.lower():
                    raise RuntimeError(
                        f"Forbidden command detected: {forbidden}"
                    )

        # Execute via tool executor if available
        if self.tool_executor:
            return await self.tool_executor.execute(tool_name, tool_input)

        # Fallback: execute via agent's tool methods
        tool_def = self.context.tools.tools.get(tool_name)
        if tool_def:
            if hasattr(tool_def, "call"):
                result = await tool_def.call(**tool_input)
                return result
            elif hasattr(tool_def, "__call__"):
                return await tool_def(**tool_input)

        raise RuntimeError(f"Tool not found: {tool_name}")

    # ========================================================================
    # Phase 6: Recursive Turn Management
    # ========================================================================

    async def _phase6_turn_complete(self) -> TurnCompleteEvent:
        """Finalize the turn and prepare for potential continuation.

        Adds the assistant message to history and returns turn completion.
        """
        turn = self._turn_state

        # Convert accumulator to CliMessage
        assistant_msg = turn.accumulator.to_cli_message()

        # Add tool results as content blocks
        for result in turn.tool_results:
            assistant_msg.add_tool_result(result)

        # Track metrics
        if assistant_msg.token_usage:
            self.context.track_cost(
                cost_usd=assistant_msg.cost_usd or 0.0,
                input_tokens=assistant_msg.token_usage.input_tokens,
                output_tokens=assistant_msg.token_usage.output_tokens,
            )

        # Add to history
        self.context.history.add_message(assistant_msg)

        return TurnCompleteEvent(
            turn_number=turn.turn_number,
            total_duration_ms=turn.elapsed_ms(),
            turn_id=str(turn.turn_number),
        )

    # ========================================================================
    # Main Loop Entry Point
    # ========================================================================

    async def run(
        self, user_input: str
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run the six-phase agent loop.

        This is the main entry point - an async generator that yields
        events for the UI to process.

        Example:
            loop = AgentLoop(agent, context)
            async for event in loop.run("List the files"):
                if isinstance(event, ContentDeltaEvent):
                    print(event.delta, end="")
                elif isinstance(event, ToolConfirmationEvent):
                    event.is_confirmed = await ask_user(event.reason)
        """
        # Start ANR detection
        if self._anr_detector:
            await self._anr_detector.start_async()

        try:
            # Use backpressure controller if enabled
            if self._backpressure:
                async for event in self._run_with_backpressure(user_input):
                    yield event
            else:
                async for event in self._run_without_backpressure(user_input):
                    yield event
        except Exception as e:
            yield ErrorEvent(
                error_type="runtime_error",
                message=str(e),
                recoverable=True,
            )
        finally:
            # Stop ANR detection
            if self._anr_detector:
                self._anr_detector.stop()
            # Close backpressure controller
            if self._backpressure:
                self._backpressure.close()

    async def _run_without_backpressure(
        self, user_input: str
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run the agent loop without backpressure control."""
        # Phase 1: Initialize turn
        self._heartbeat()
        turn = await self._phase1_turn_init(user_input)

        # Phase 2: Assemble prompt
        self._heartbeat()
        messages = await self._phase2_assemble_prompt()

        # Phase 3 & 4: Stream and process
        self._heartbeat()
        stream = self._phase3_init_stream(messages)
        tool_calls: list[ToolUseBlock] = []

        async for event in self._phase4_process_stream(stream):
            self._heartbeat()
            yield event

            # Collect tool calls for execution
            if isinstance(event, ToolUseCompleteEvent):
                tool_calls.append(
                    ToolUseBlock(
                        id=event.tool_use_id,
                        name=event.tool_name,
                        input=event.tool_input,
                    )
                )

        # Phase 5: Execute tools
        if tool_calls:
            async for event in self._phase5_execute_tools(tool_calls):
                self._heartbeat()
                yield event

                # Collect results
                if isinstance(event, ToolResultEvent):
                    turn.tool_results.append(
                        ToolResultBlock(
                            tool_use_id=event.tool_use_id,
                            content=str(event.result)
                            if not event.is_error
                            else event.error_message or "",
                            is_error=event.is_error,
                        )
                    )

        # Phase 6: Complete turn
        self._heartbeat()
        complete_event = await self._phase6_turn_complete()
        yield complete_event

    async def _run_with_backpressure(
        self, user_input: str
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run the agent loop with backpressure control.

        Events are buffered and yielded with priority-based flow control.
        Low-priority events (progress updates) may be dropped when the
        buffer is full, while critical events (errors, completions) are
        always preserved.
        """
        # Start the producer task
        producer_task = asyncio.create_task(
            self._produce_events(user_input)
        )

        try:
            # Consume events from backpressure controller
            async for event in self._backpressure.events():
                yield event
        finally:
            # Ensure producer task is cleaned up
            if not producer_task.done():
                producer_task.cancel()
                try:
                    await producer_task
                except asyncio.CancelledError:
                    pass

    async def _produce_events(self, user_input: str) -> None:
        """Produce events and add them to the backpressure controller."""
        try:
            # Phase 1: Initialize turn
            self._heartbeat()
            turn = await self._phase1_turn_init(user_input)

            # Phase 2: Assemble prompt
            self._heartbeat()
            messages = await self._phase2_assemble_prompt()

            # Phase 3 & 4: Stream and process
            self._heartbeat()
            stream = self._phase3_init_stream(messages)
            tool_calls: list[ToolUseBlock] = []

            async for event in self._phase4_process_stream(stream):
                self._heartbeat()
                priority = get_priority_for_event(event)
                await self._backpressure.add_event(event, priority)

                # Collect tool calls for execution
                if isinstance(event, ToolUseCompleteEvent):
                    tool_calls.append(
                        ToolUseBlock(
                            id=event.tool_use_id,
                            name=event.tool_name,
                            input=event.tool_input,
                        )
                    )

            # Phase 5: Execute tools
            if tool_calls:
                async for event in self._phase5_execute_tools(tool_calls):
                    self._heartbeat()
                    priority = get_priority_for_event(event)
                    await self._backpressure.add_event(event, priority)

                    # Collect results
                    if isinstance(event, ToolResultEvent):
                        turn.tool_results.append(
                            ToolResultBlock(
                                tool_use_id=event.tool_use_id,
                                content=str(event.result)
                                if not event.is_error
                                else event.error_message or "",
                                is_error=event.is_error,
                            )
                        )

            # Phase 6: Complete turn
            self._heartbeat()
            complete_event = await self._phase6_turn_complete()
            priority = get_priority_for_event(complete_event)
            await self._backpressure.add_event(complete_event, priority)

        except Exception as e:
            # Yield error event with critical priority
            error_event = ErrorEvent(
                error_type="runtime_error",
                message=str(e),
                recoverable=True,
            )
            await self._backpressure.add_event(
                error_event, EventPriority.CRITICAL
            )
        finally:
            # Signal completion
            self._backpressure.close()

    async def run_continuous(
        self, user_input: str, max_turns: Optional[int] = None
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run multiple turns until completion or max turns reached.

        This handles the recursive nature where tool results are fed back
        to the LLM for further processing.
        """
        max_turns = max_turns or self.config.max_turns
        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1
            turn_complete = False

            async for event in self.run(user_input):
                yield event

                if isinstance(event, TurnCompleteEvent):
                    turn_complete = True

                # Check if we need another turn (tool results present)
                if isinstance(event, ToolResultEvent):
                    # Will need another iteration
                    pass

            if not turn_complete:
                # Error occurred
                break

            # Check if there are pending tool results to process
            if not self._turn_state.tool_results:
                # No more tool results, conversation is complete
                break

            # Prepare next turn with tool results
            user_input = self._format_tool_results_for_llm(
                self._turn_state.tool_results
            )
            self._turn_state.tool_results = []

    def _format_tool_results_for_llm(
        self, results: list[ToolResultBlock]
    ) -> str:
        """Format tool results for the next LLM turn."""
        parts = ["Tool results:"]
        for result in results:
            content = (
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )
            status = "ERROR" if result.is_error else "OK"
            parts.append(f"[{result.tool_use_id}] {status}: {content[:500]}")
        return "\n".join(parts)

    # ========================================================================
    # ANR Detection Helpers
    # ========================================================================

    def _heartbeat(self) -> None:
        """Send heartbeat to ANR detector."""
        if self._anr_detector:
            self._anr_detector.heartbeat()

    def _on_anr_detected(self, event: ANREvent) -> None:
        """Handle ANR detection."""
        import logging

        logger = logging.getLogger("adorable.anr")
        logger.error(
            f"ANR detected in AgentLoop: {event.elapsed_ms:.0f}ms "
            f"(threshold: {event.threshold_ms:.0f}ms)"
        )
        logger.error(f"Last heartbeat: {event.last_heartbeat}")
        logger.error(f"Stack trace:\n{event.stack_trace}")

        # Could also:
        # - Emit ANR event to UI via yield
        # - Cancel current operation
        # - Send telemetry
        # - Trigger recovery
