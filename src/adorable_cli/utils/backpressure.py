"""Streaming backpressure controller for high-volume event handling.

Claude Code's backpressure system:
- Buffers events when processing can't keep up
- Yields immediately for high-priority events
- Drops low-priority events when buffer is full
- Provides flow control for streaming pipelines

Usage:
    controller = BackpressureController(buffer_size=1000)

    # Add events
    await controller.add_event(event)

    # Consume events
    async for event in controller.events():
        process(event)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Callable, Optional, TypeVar

from adorable_cli.models.events import AgentEvent


class EventPriority(Enum):
    """Priority levels for events."""

    CRITICAL = 0  # Never drop (errors, completions)
    HIGH = 1  # Prefer keeping (tool starts, confirmations)
    MEDIUM = 2  # Standard priority (content deltas)
    LOW = 3  # Drop first if needed (progress updates)


@dataclass
class BackpressureStats:
    """Statistics for backpressure controller."""

    total_added: int = 0
    total_yielded: int = 0
    total_dropped: int = 0
    buffer_high_water_mark: int = 0
    current_buffer_size: int = 0

    def record_added(self) -> None:
        """Record an event being added."""
        self.total_added += 1

    def record_yielded(self) -> None:
        """Record an event being yielded."""
        self.total_yielded += 1

    def record_dropped(self) -> None:
        """Record an event being dropped."""
        self.total_dropped += 1

    def update_high_water_mark(self, current_size: int) -> None:
        """Update the high water mark."""
        self.buffer_high_water_mark = max(
            self.buffer_high_water_mark, current_size
        )
        self.current_buffer_size = current_size


@dataclass
class PrioritizedEvent:
    """An event with priority information."""

    event: AgentEvent
    priority: EventPriority
    timestamp: float = field(default_factory=lambda: _default_timestamp())

    def __lt__(self, other: PrioritizedEvent) -> bool:
        """Compare for priority queue (lower priority value = higher priority)."""
        return self.priority.value < other.priority.value


def _default_timestamp() -> float:
    try:
        return asyncio.get_running_loop().time()
    except RuntimeError:
        return time.monotonic()


class BackpressureController:
    """Controls event flow with backpressure handling.

    When events are produced faster than they can be consumed,
    this controller:
    1. Buffers events up to a limit
    2. Drops low-priority events when buffer is full
    3. Yields high-priority events immediately
    4. Provides flow control via pause/resume

    Example:
        controller = BackpressureController(buffer_size=1000)

        # Producer
        async def producer():
            for event in stream:
                priority = get_priority(event)
                await controller.add_event(event, priority)

        # Consumer
        async def consumer():
            async for event in controller.events():
                await process(event)
    """

    def __init__(
        self,
        buffer_size: int = 1000,
        drop_threshold: float = 0.9,
        pause_threshold: float = 0.8,
        resume_threshold: float = 0.5,
    ):
        """Initialize backpressure controller.

        Args:
            buffer_size: Maximum buffer size
            drop_threshold: Drop low-priority events above this fill level
            pause_threshold: Signal pause above this fill level
            resume_threshold: Signal resume below this fill level
        """
        self.buffer_size = buffer_size
        self.drop_threshold = int(buffer_size * drop_threshold)
        self.pause_threshold = int(buffer_size * pause_threshold)
        self.resume_threshold = int(buffer_size * resume_threshold)

        # Priority queue: deque with manual priority ordering
        self._buffer: deque[PrioritizedEvent] = deque()
        self._event_available = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

        self._stats = BackpressureStats()
        self._closed = False

    async def add_event(
        self,
        event: AgentEvent,
        priority: EventPriority = EventPriority.MEDIUM,
        block: bool = True,
    ) -> bool:
        """Add an event to the buffer.

        Args:
            event: Event to add
            priority: Event priority
            block: If True, wait for space; if False, drop immediately if full

        Returns:
            True if event was added, False if dropped
        """
        if self._closed:
            return False

        self._stats.record_added()

        # High priority events: add immediately, dropping low priority if needed
        if priority == EventPriority.CRITICAL:
            # Make room if needed by dropping lowest priority events
            while len(self._buffer) >= self.buffer_size:
                self._drop_lowest_priority()
            self._add_to_buffer(PrioritizedEvent(event, priority))
            return True

        # High priority: add unless completely full
        if priority == EventPriority.HIGH:
            if len(self._buffer) >= self.buffer_size:
                if block:
                    await self._wait_for_space()
                else:
                    self._stats.record_dropped()
                    return False
            self._add_to_buffer(PrioritizedEvent(event, priority))
            return True

        # Medium/Low priority: drop if above threshold
        if len(self._buffer) >= self.drop_threshold:
            if priority == EventPriority.LOW:
                # Always drop low priority above threshold
                self._stats.record_dropped()
                return False
            # Medium priority: check if we can drop lower priority events
            if not self._make_room_by_dropping_lower(priority):
                if block:
                    await self._wait_for_space()
                else:
                    self._stats.record_dropped()
                    return False

        # Check if we should pause producers
        if len(self._buffer) >= self.pause_threshold:
            self._pause_event.clear()

        self._add_to_buffer(PrioritizedEvent(event, priority))
        return True

    def _add_to_buffer(self, pevent: PrioritizedEvent) -> None:
        """Add event to buffer maintaining priority order."""
        # Insert in priority order (lower value = higher priority)
        # This keeps the deque sorted by priority
        inserted = False
        for i, existing in enumerate(self._buffer):
            if pevent.priority.value < existing.priority.value:
                self._buffer.insert(i, pevent)
                inserted = True
                break

        if not inserted:
            self._buffer.append(pevent)

        self._stats.update_high_water_mark(len(self._buffer))
        self._event_available.set()

    def _drop_lowest_priority(self) -> bool:
        """Drop the lowest priority event from buffer.

        Returns:
            True if an event was dropped
        """
        if not self._buffer:
            return False

        # Drop from the end (lowest priority due to ordering)
        dropped = self._buffer.pop()
        self._stats.record_dropped()

        # Signal space available
        if len(self._buffer) < self.resume_threshold:
            self._pause_event.set()

        return True

    def _make_room_by_dropping_lower(self, min_priority: EventPriority) -> bool:
        """Try to make room by dropping lower priority events.

        Returns:
            True if room was made
        """
        # Look for lower priority events at the end
        for i in range(len(self._buffer) - 1, -1, -1):
            if self._buffer[i].priority.value > min_priority.value:
                del self._buffer[i]
                self._stats.record_dropped()
                return True
        return False

    async def _wait_for_space(self) -> None:
        """Wait until there's space in the buffer."""
        while len(self._buffer) >= self.buffer_size and not self._closed:
            self._pause_event.clear()
            await self._pause_event.wait()

    async def events(self) -> AsyncGenerator[AgentEvent, None]:
        """Async generator yielding events from the buffer.

        Yields:
            AgentEvent objects in priority order
        """
        while not self._closed or self._buffer:
            if not self._buffer:
                self._event_available.clear()
                try:
                    await asyncio.wait_for(
                        self._event_available.wait(), timeout=0.1
                    )
                except asyncio.TimeoutError:
                    continue

            if self._buffer:
                pevent = self._buffer.popleft()
                self._stats.record_yielded()

                # Signal space available
                if len(self._buffer) < self.resume_threshold:
                    self._pause_event.set()

                yield pevent.event

    def should_pause(self) -> bool:
        """Check if producers should pause."""
        return len(self._buffer) >= self.pause_threshold

    async def wait_for_resume(self) -> None:
        """Wait until producers should resume."""
        if not self._pause_event.is_set():
            await self._pause_event.wait()

    def close(self) -> None:
        """Close the controller, signaling no more events."""
        self._closed = True
        self._event_available.set()
        self._pause_event.set()

    def get_stats(self) -> BackpressureStats:
        """Get current statistics."""
        self._stats.current_buffer_size = len(self._buffer)
        return self._stats

    @property
    def is_closed(self) -> bool:
        """Check if controller is closed."""
        return self._closed

    @property
    def buffer_fill_level(self) -> float:
        """Current buffer fill level (0.0 to 1.0)."""
        return len(self._buffer) / self.buffer_size


class StreamBackpressureAdapter:
    """Adapts backpressure control to an async generator.

    Wraps an async generator with backpressure control,
    buffering events and handling flow control.

    Example:
        async def raw_stream():
            while True:
                yield event

        adapter = StreamBackpressureAdapter(raw_stream())
        async for event in adapter:
            process(event)

        # Check stats
        print(adapter.controller.get_stats())
    """

    def __init__(
        self,
        source: AsyncGenerator[AgentEvent, None],
        buffer_size: int = 1000,
        priority_fn: Optional[Callable[[AgentEvent], EventPriority]] = None,
    ):
        """Initialize adapter.

        Args:
            source: Source async generator
            buffer_size: Buffer size
            priority_fn: Function to determine event priority
        """
        self.source = source
        self.controller = BackpressureController(buffer_size)
        self.priority_fn = priority_fn or self._default_priority
        self._task: Optional[asyncio.Task] = None

    @staticmethod
    def _default_priority(event: AgentEvent) -> EventPriority:
        """Default priority assignment based on event type."""
        from adorable_cli.models.events import (
            ErrorEvent,
            MessageCompleteEvent,
            ToolConfirmationEvent,
            ToolExecutionProgressEvent,
            TurnCompleteEvent,
        )

        if isinstance(event, ErrorEvent):
            return EventPriority.CRITICAL
        if isinstance(event, (TurnCompleteEvent, MessageCompleteEvent)):
            return EventPriority.CRITICAL
        if isinstance(event, ToolConfirmationEvent):
            return EventPriority.HIGH
        if isinstance(event, ToolExecutionProgressEvent):
            return EventPriority.LOW
        return EventPriority.MEDIUM

    async def _pump(self) -> None:
        """Pump events from source to controller."""
        try:
            async for event in self.source:
                priority = self.priority_fn(event)
                await self.controller.add_event(event, priority, block=True)
        finally:
            self.controller.close()

    def __aiter__(self) -> AsyncGenerator[AgentEvent, None]:
        """Start pumping and return event iterator."""
        self._task = asyncio.create_task(self._pump())
        return self.controller.events()

    async def close(self) -> None:
        """Close the adapter."""
        self.controller.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# Convenience functions


def get_priority_for_event(event: AgentEvent) -> EventPriority:
    """Get default priority for an event type.

    This is the standard priority assignment used throughout the system.
    """
    from adorable_cli.models.events import (
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
        ToolUseStartEvent,
        TurnCompleteEvent,
    )

    # Critical: Errors and completion events
    if isinstance(event, (ErrorEvent, TurnCompleteEvent, MessageCompleteEvent)):
        return EventPriority.CRITICAL

    # High: User interaction events
    if isinstance(event, (ToolConfirmationEvent, ToolUseStartEvent)):
        return EventPriority.HIGH

    # Medium: Content and results
    if isinstance(
        event,
        (
            ContentDeltaEvent,
            ThinkingDeltaEvent,
            ToolResultEvent,
            ToolUseCompleteEvent,
            ToolExecutionStartEvent,
        ),
    ):
        return EventPriority.MEDIUM

    # Low: Progress updates
    if isinstance(event, (ToolExecutionProgressEvent, CompactionEvent)):
        return EventPriority.LOW

    return EventPriority.MEDIUM
