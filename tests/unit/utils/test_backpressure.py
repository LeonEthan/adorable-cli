"""Tests for streaming backpressure controller."""

import asyncio
from collections.abc import AsyncGenerator

import pytest

from adorable_cli.models.events import (
    ContentDeltaEvent,
    ErrorEvent,
    MessageCompleteEvent,
    ToolExecutionProgressEvent,
)
from adorable_cli.utils.backpressure import (
    BackpressureController,
    BackpressureStats,
    EventPriority,
    PrioritizedEvent,
    StreamBackpressureAdapter,
    get_priority_for_event,
)


class TestEventPriority:
    """Test EventPriority enum."""

    def test_priority_ordering(self):
        """Test that priorities are ordered correctly."""
        assert EventPriority.CRITICAL.value < EventPriority.HIGH.value
        assert EventPriority.HIGH.value < EventPriority.MEDIUM.value
        assert EventPriority.MEDIUM.value < EventPriority.LOW.value

    def test_priority_values(self):
        """Test priority values."""
        assert EventPriority.CRITICAL.value == 0
        assert EventPriority.HIGH.value == 1
        assert EventPriority.MEDIUM.value == 2
        assert EventPriority.LOW.value == 3


class TestBackpressureStats:
    """Test BackpressureStats tracking."""

    def test_initial_stats(self):
        """Test initial stats are zero."""
        stats = BackpressureStats()
        assert stats.total_added == 0
        assert stats.total_yielded == 0
        assert stats.total_dropped == 0
        assert stats.buffer_high_water_mark == 0
        assert stats.current_buffer_size == 0

    def test_record_added(self):
        """Test recording added events."""
        stats = BackpressureStats()
        stats.record_added()
        assert stats.total_added == 1
        stats.record_added()
        assert stats.total_added == 2

    def test_record_yielded(self):
        """Test recording yielded events."""
        stats = BackpressureStats()
        stats.record_yielded()
        assert stats.total_yielded == 1

    def test_record_dropped(self):
        """Test recording dropped events."""
        stats = BackpressureStats()
        stats.record_dropped()
        assert stats.total_dropped == 1

    def test_update_high_water_mark(self):
        """Test high water mark tracking."""
        stats = BackpressureStats()
        stats.update_high_water_mark(10)
        assert stats.buffer_high_water_mark == 10
        assert stats.current_buffer_size == 10

        stats.update_high_water_mark(5)
        assert stats.buffer_high_water_mark == 10  # Not reduced
        assert stats.current_buffer_size == 5

        stats.update_high_water_mark(20)
        assert stats.buffer_high_water_mark == 20  # Increased
        assert stats.current_buffer_size == 20


class TestPrioritizedEvent:
    """Test PrioritizedEvent dataclass."""

    def test_creation(self):
        """Test creating a prioritized event."""
        event = ContentDeltaEvent(delta="test")
        pe = PrioritizedEvent(event, EventPriority.HIGH)

        assert pe.event == event
        assert pe.priority == EventPriority.HIGH
        assert pe.timestamp > 0

    def test_comparison(self):
        """Test priority comparison."""
        event = ContentDeltaEvent(delta="test")

        pe_critical = PrioritizedEvent(event, EventPriority.CRITICAL)
        pe_high = PrioritizedEvent(event, EventPriority.HIGH)
        pe_low = PrioritizedEvent(event, EventPriority.LOW)

        assert pe_critical < pe_high
        assert pe_high < pe_low
        assert pe_critical < pe_low


class TestBackpressureController:
    """Test BackpressureController."""

    @pytest.mark.asyncio
    async def test_add_single_event(self):
        """Test adding a single event."""
        controller = BackpressureController(buffer_size=10)
        event = ContentDeltaEvent(delta="test")

        result = await controller.add_event(event, EventPriority.MEDIUM)
        assert result is True

        stats = controller.get_stats()
        assert stats.total_added == 1

        controller.close()

    @pytest.mark.asyncio
    async def test_event_ordering_by_priority(self):
        """Test that events are yielded in priority order."""
        controller = BackpressureController(buffer_size=10)

        # Add events in reverse priority order
        low = ContentDeltaEvent(delta="low")
        medium = ContentDeltaEvent(delta="medium")
        high = ContentDeltaEvent(delta="high")
        critical = ErrorEvent(message="critical")

        await controller.add_event(low, EventPriority.LOW)
        await controller.add_event(medium, EventPriority.MEDIUM)
        await controller.add_event(high, EventPriority.HIGH)
        await controller.add_event(critical, EventPriority.CRITICAL)

        controller.close()

        # Collect events
        events = []
        async for e in controller.events():
            events.append(e)

        # Should be in priority order
        assert len(events) == 4
        assert isinstance(events[0], ErrorEvent)
        assert events[1].delta == "high"
        assert events[2].delta == "medium"
        assert events[3].delta == "low"

    @pytest.mark.asyncio
    async def test_critical_event_makes_room(self):
        """Test that critical events make room by dropping low priority."""
        controller = BackpressureController(buffer_size=2)

        # Fill buffer
        low1 = ContentDeltaEvent(delta="low1")
        low2 = ContentDeltaEvent(delta="low2")
        await controller.add_event(low1, EventPriority.LOW)
        await controller.add_event(low2, EventPriority.LOW)

        # Add critical event (should drop low priority)
        critical = ErrorEvent(message="critical")
        result = await controller.add_event(critical, EventPriority.CRITICAL)
        assert result is True

        stats = controller.get_stats()
        assert stats.total_dropped >= 1

        controller.close()

    @pytest.mark.asyncio
    async def test_low_priority_dropped_when_full(self):
        """Test that low priority events are dropped when buffer is full."""
        controller = BackpressureController(buffer_size=10, drop_threshold=0.5)

        # Fill to drop threshold
        for i in range(6):
            event = ContentDeltaEvent(delta=f"medium-{i}")
            await controller.add_event(event, EventPriority.MEDIUM)

        # Add low priority - should be dropped
        low = ContentDeltaEvent(delta="low")
        result = await controller.add_event(low, EventPriority.LOW)
        assert result is False

        stats = controller.get_stats()
        assert stats.total_dropped == 1

        controller.close()

    @pytest.mark.asyncio
    async def test_high_priority_blocks_when_full(self):
        """Test that high priority events block when buffer is completely full."""
        controller = BackpressureController(buffer_size=2)

        # Fill buffer with medium priority
        for i in range(2):
            event = ContentDeltaEvent(delta=f"medium-{i}")
            await controller.add_event(event, EventPriority.MEDIUM)

        # Try to add high priority without blocking - should fail
        high = ContentDeltaEvent(delta="high")
        result = await controller.add_event(high, EventPriority.HIGH, block=False)
        assert result is False

        controller.close()

    @pytest.mark.asyncio
    async def test_consumer_yields_events(self):
        """Test that consumer yields events from buffer."""
        controller = BackpressureController(buffer_size=10)

        # Add some events
        for i in range(3):
            event = ContentDeltaEvent(delta=f"content-{i}")
            await controller.add_event(event, EventPriority.MEDIUM)

        controller.close()

        # Consume all events
        events = []
        async for e in controller.events():
            events.append(e)

        assert len(events) == 3

        stats = controller.get_stats()
        assert stats.total_yielded == 3

    @pytest.mark.asyncio
    async def test_pause_resume_thresholds(self):
        """Test pause and resume signaling."""
        controller = BackpressureController(
            buffer_size=100,
            pause_threshold=0.8,
            resume_threshold=0.5,
        )

        # Initially not paused
        assert not controller.should_pause()

        # Fill to pause threshold
        for i in range(80):
            event = ContentDeltaEvent(delta=f"content-{i}")
            await controller.add_event(event, EventPriority.MEDIUM)

        assert controller.should_pause()

        # Consume events down to resume threshold
        count = 0
        async for e in controller.events():
            count += 1
            if count >= 35:
                break

        # Should be below resume threshold
        assert len(controller._buffer) < 50

        controller.close()

    @pytest.mark.asyncio
    async def test_closed_controller_rejects_events(self):
        """Test that closed controller rejects new events."""
        controller = BackpressureController(buffer_size=10)
        controller.close()

        event = ContentDeltaEvent(delta="test")
        result = await controller.add_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_buffer_fill_level(self):
        """Test buffer fill level calculation."""
        controller = BackpressureController(buffer_size=100)

        assert controller.buffer_fill_level == 0.0

        for i in range(50):
            event = ContentDeltaEvent(delta="test")
            await controller.add_event(event, EventPriority.MEDIUM)

        assert controller.buffer_fill_level == 0.5

        controller.close()

    @pytest.mark.asyncio
    async def test_make_room_by_dropping_lower(self):
        """Test making room by dropping lower priority events."""
        controller = BackpressureController(buffer_size=10)

        # Add low priority events
        for i in range(3):
            event = ContentDeltaEvent(delta="low")
            await controller.add_event(event, EventPriority.LOW)

        # Make room for medium priority
        result = controller._make_room_by_dropping_lower(EventPriority.MEDIUM)
        assert result is True

        stats = controller.get_stats()
        assert stats.total_dropped == 1

        controller.close()

    @pytest.mark.asyncio
    async def test_wait_for_space_timeout(self):
        """Test that waiting for space can timeout."""
        controller = BackpressureController(buffer_size=1)

        # Fill buffer
        event = ContentDeltaEvent(delta="test")
        await controller.add_event(event, EventPriority.CRITICAL)

        # Try to add another critical event (should wait then drop)
        # But since we're not consuming, it will need to drop
        event2 = ContentDeltaEvent(delta="test2")

        # This should drop the existing event to make room
        result = await asyncio.wait_for(
            controller.add_event(event2, EventPriority.CRITICAL),
            timeout=1.0,
        )
        assert result is True

        controller.close()


class TestStreamBackpressureAdapter:
    """Test StreamBackpressureAdapter."""

    @pytest.mark.asyncio
    async def test_adapter_wraps_generator(self):
        """Test that adapter wraps an async generator."""

        async def source() -> AsyncGenerator:
            for i in range(3):
                yield ContentDeltaEvent(delta=f"content-{i}")

        adapter = StreamBackpressureAdapter(source(), buffer_size=10)

        # Collect events
        events = []
        async for e in adapter:
            events.append(e)

        await adapter.close()

        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_default_priority_assignment(self):
        """Test default priority assignment based on event type."""

        async def source() -> AsyncGenerator:
            yield ErrorEvent(message="test error")
            yield ContentDeltaEvent(delta="test")
            yield ToolExecutionProgressEvent(message="50%")

        adapter = StreamBackpressureAdapter(source(), buffer_size=10)

        events = []
        priorities = []
        async for e in adapter:
            events.append(e)
            priorities.append(adapter.priority_fn(e))

        await adapter.close()

        assert priorities[0] == EventPriority.CRITICAL  # ErrorEvent
        assert priorities[1] == EventPriority.MEDIUM  # ContentDeltaEvent
        assert priorities[2] == EventPriority.LOW  # ToolExecutionProgressEvent

    @pytest.mark.asyncio
    async def test_custom_priority_function(self):
        """Test custom priority function."""

        async def source() -> AsyncGenerator:
            yield ContentDeltaEvent(delta="test")

        def custom_priority(event):
            return EventPriority.HIGH

        adapter = StreamBackpressureAdapter(
            source(), buffer_size=10, priority_fn=custom_priority
        )

        events = []
        async for e in adapter:
            events.append(e)
            assert adapter.priority_fn(e) == EventPriority.HIGH

        await adapter.close()

    @pytest.mark.asyncio
    async def test_adapter_close_cancels_pump(self):
        """Test that closing adapter cancels the pump task."""

        async def slow_source() -> AsyncGenerator:
            for i in range(100):
                yield ContentDeltaEvent(delta="test")
                await asyncio.sleep(0.1)

        adapter = StreamBackpressureAdapter(slow_source(), buffer_size=10)

        # Start iteration
        iterator = adapter.__aiter__()

        # Close immediately
        await adapter.close()

        assert adapter.controller.is_closed


class TestGetPriorityForEvent:
    """Test get_priority_for_event function."""

    def test_critical_events(self):
        """Test that error and completion events are critical."""
        error = ErrorEvent(message="test")
        complete = MessageCompleteEvent()

        assert get_priority_for_event(error) == EventPriority.CRITICAL
        assert get_priority_for_event(complete) == EventPriority.CRITICAL

    def test_high_priority_events(self):
        """Test high priority events."""
        from adorable_cli.models.events import (
            ToolConfirmationEvent,
            ToolUseStartEvent,
        )

        confirm = ToolConfirmationEvent(tool_name="test")
        start = ToolUseStartEvent(tool_name="test")

        assert get_priority_for_event(confirm) == EventPriority.HIGH
        assert get_priority_for_event(start) == EventPriority.HIGH

    def test_low_priority_events(self):
        """Test low priority events."""
        progress = ToolExecutionProgressEvent(message="50%")

        assert get_priority_for_event(progress) == EventPriority.LOW

    def test_medium_priority_default(self):
        """Test that unknown events get medium priority."""
        from adorable_cli.models.events import AgentEvent

        class UnknownEvent:
            pass

        unknown = UnknownEvent()
        assert get_priority_for_event(unknown) == EventPriority.MEDIUM


class TestBackpressureIntegration:
    """Integration tests for backpressure system."""

    @pytest.mark.asyncio
    async def test_producer_consumer_pattern(self):
        """Test producer-consumer pattern with backpressure."""
        controller = BackpressureController(buffer_size=100)

        async def producer():
            for i in range(50):
                event = ContentDeltaEvent(delta=f"content-{i}")
                await controller.add_event(event, EventPriority.MEDIUM)
            controller.close()

        async def consumer():
            events = []
            async for e in controller.events():
                events.append(e)
                await asyncio.sleep(0.001)  # Simulate processing
            return events

        # Run producer and consumer concurrently
        producer_task = asyncio.create_task(producer())
        consumer_task = asyncio.create_task(consumer())

        events = await consumer_task
        await producer_task

        assert len(events) == 50

        stats = controller.get_stats()
        assert stats.total_added == 50
        assert stats.total_yielded == 50
        assert stats.total_dropped == 0

    @pytest.mark.asyncio
    async def test_backpressure_under_load(self):
        """Test backpressure behavior under high load."""
        controller = BackpressureController(
            buffer_size=10,
            drop_threshold=0.8,
        )

        async def fast_producer():
            # Produce events faster than they can be consumed
            for i in range(100):
                event = ToolExecutionProgressEvent(message=f"{i}%")
                await controller.add_event(event, EventPriority.LOW)
            controller.close()

        async def slow_consumer():
            events = []
            async for e in controller.events():
                events.append(e)
                await asyncio.sleep(0.01)  # Slow processing
            return events

        producer_task = asyncio.create_task(fast_producer())
        consumer_task = asyncio.create_task(slow_consumer())

        events = await consumer_task
        await producer_task

        stats = controller.get_stats()
        # Should have dropped some low priority events
        assert stats.total_dropped > 0
        assert stats.total_added == 100
        assert stats.total_yielded < 100

    @pytest.mark.asyncio
    async def test_critical_events_never_dropped(self):
        """Test that critical events are never dropped."""
        controller = BackpressureController(buffer_size=5, drop_threshold=0.6)

        async def producer():
            # Fill buffer with low priority
            for i in range(5):
                event = ToolExecutionProgressEvent(message=f"{i}%")
                await controller.add_event(event, EventPriority.LOW)

            # Critical event should be added by dropping low priority
            critical = ErrorEvent(message="critical error")
            result = await controller.add_event(critical, EventPriority.CRITICAL)
            assert result is True

            controller.close()

        async def consumer():
            events = []
            async for e in controller.events():
                events.append(e)
            return events

        producer_task = asyncio.create_task(producer())
        events = await consumer()
        await producer_task

        # Should have the critical event
        assert any(isinstance(e, ErrorEvent) for e in events)

        stats = controller.get_stats()
        # Some low priority events should have been dropped
        assert stats.total_dropped > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
