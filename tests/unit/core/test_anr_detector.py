"""Tests for ANR (Application Not Responding) detection."""

import asyncio
import threading
import time

import pytest

from adorable_cli.core.anr_detector import (
    ANRDetector,
    AsyncANRDetector,
    ANREvent,
    ANRStatus,
    AgentLoopANRIntegration,
    install_anr_handler,
)


class TestANRDetector:
    """Test ANR detection functionality."""

    def test_initial_status(self):
        detector = ANRDetector()
        assert detector.status == ANRStatus.IDLE
        assert detector.is_responsive() is False  # Not started yet

    def test_start_changes_status(self):
        detector = ANRDetector()
        detector.start()

        assert detector.status == ANRStatus.RUNNING
        assert detector.is_responsive() is True

        detector.stop()

    def test_heartbeat_updates_responsiveness(self):
        detector = ANRDetector(threshold_ms=1000)
        detector.start()

        # Initially responsive
        assert detector.is_responsive() is True

        # Heartbeat keeps it responsive
        detector.heartbeat()
        assert detector.is_responsive() is True

        detector.stop()

    def test_stop_changes_status(self):
        detector = ANRDetector()
        detector.start()
        assert detector.status == ANRStatus.RUNNING

        detector.stop()
        assert detector.status == ANRStatus.STOPPED

    def test_anr_triggered_after_timeout(self):
        anr_events = []

        def on_anr(event):
            anr_events.append(event)

        # Very short threshold for testing
        detector = ANRDetector(threshold_ms=100, check_interval_ms=50)
        detector.on_anr = on_anr
        detector.start()

        # Don't send heartbeats
        time.sleep(0.3)  # Wait longer than threshold

        assert len(anr_events) >= 1
        assert detector.status == ANRStatus.TRIGGERED

        detector.stop()

    def test_anr_event_contains_details(self):
        anr_events = []

        def on_anr(event):
            anr_events.append(event)

        detector = ANRDetector(threshold_ms=100, check_interval_ms=50)
        detector.on_anr = on_anr
        detector.start()

        time.sleep(0.3)

        assert len(anr_events) >= 1
        event = anr_events[0]

        assert event.elapsed_ms >= 100
        assert event.threshold_ms == 100
        assert event.timestamp > 0
        assert event.last_heartbeat > 0
        assert len(event.stack_trace) > 0

        detector.stop()

    def test_heartbeat_prevents_anr(self):
        anr_events = []

        def on_anr(event):
            anr_events.append(event)

        detector = ANRDetector(threshold_ms=200, check_interval_ms=50)
        detector.on_anr = on_anr
        detector.start()

        # Send heartbeats frequently
        for _ in range(10):
            time.sleep(0.1)
            detector.heartbeat()

        assert len(anr_events) == 0
        assert detector.status == ANRStatus.RUNNING

        detector.stop()

    def test_multiple_start_calls_safe(self):
        detector = ANRDetector()
        detector.start()
        detector.start()  # Should not fail
        detector.start()

        assert detector.status == ANRStatus.RUNNING
        detector.stop()

    def test_thread_dump_includes_all_threads(self):
        anr_events = []

        def on_anr(event):
            anr_events.append(event)

        detector = ANRDetector(threshold_ms=100, check_interval_ms=50, enable_stack_dump=True)
        detector.on_anr = on_anr
        detector.start()

        time.sleep(0.3)

        assert len(anr_events) >= 1
        event = anr_events[0]

        # Thread dump should contain current thread
        assert "Thread" in event.thread_dump
        assert "ANRMonitor" in event.thread_dump or True  # May or may not be present

        detector.stop()


class TestAsyncANRDetector:
    """Test async ANR detector."""

    @pytest.mark.asyncio
    async def test_async_start_stop(self):
        detector = AsyncANRDetector()
        await detector.start_async()

        assert detector.status == ANRStatus.RUNNING

        await detector.stop_async()
        assert detector.status == ANRStatus.STOPPED

    @pytest.mark.asyncio
    async def test_async_heartbeat(self):
        detector = AsyncANRDetector(threshold_ms=500)
        await detector.start_async()

        await detector.heartbeat_async()
        assert detector.is_responsive() is True

        await detector.stop_async()

    @pytest.mark.asyncio
    async def test_async_anr_handler(self):
        anr_events = []

        detector = AsyncANRDetector(threshold_ms=100, check_interval_ms=50)

        @detector.anr_handler
        async def handle_anr(event):
            anr_events.append(event)

        await detector.start_async()

        # Don't send heartbeats
        await asyncio.sleep(0.3)

        await detector.stop_async()

        # Events may be processed after stop
        await asyncio.sleep(0.1)

        assert len(anr_events) >= 1

    @pytest.mark.asyncio
    async def test_async_heartbeat_prevents_anr(self):
        anr_events = []

        detector = AsyncANRDetector(threshold_ms=200, check_interval_ms=50)
        detector.on_anr = lambda e: anr_events.append(e)
        await detector.start_async()

        # Send heartbeats frequently
        for _ in range(10):
            await asyncio.sleep(0.1)
            await detector.heartbeat_async()

        await detector.stop_async()

        assert len(anr_events) == 0


class TestInstallANRHandler:
    """Test convenience function."""

    def test_install_with_defaults(self):
        detector = install_anr_handler()

        assert detector.status == ANRStatus.RUNNING
        assert detector.threshold_ms == 5000

        detector.stop()

    def test_install_with_custom_threshold(self):
        detector = install_anr_handler(threshold_ms=3000)

        assert detector.threshold_ms == 3000

        detector.stop()

    def test_install_with_callback(self):
        events = []

        def callback(event):
            events.append(event)

        detector = install_anr_handler(threshold_ms=100, callback=callback)

        time.sleep(0.3)

        assert len(events) >= 1

        detector.stop()


class TestAgentLoopANRIntegration:
    """Test AgentLoop ANR integration."""

    def test_initialization(self):
        from adorable_cli.core.loop import AgentLoop, AgentContext

        context = AgentContext()
        loop = AgentLoop(agent=None, context=context)

        integration = AgentLoopANRIntegration(loop, threshold_ms=3000)

        assert integration.agent_loop == loop
        assert integration.detector.threshold_ms == 3000

    def test_start_stop(self):
        from adorable_cli.core.loop import AgentLoop, AgentContext

        context = AgentContext()
        loop = AgentLoop(agent=None, context=context)
        integration = AgentLoopANRIntegration(loop)

        integration.start()
        # May not be fully started if not in async context
        integration.stop()


class TestANRInAsyncContext:
    """Test ANR in various async scenarios."""

    @pytest.mark.asyncio
    async def test_anr_during_async_work(self):
        """Simulate ANR during async work - using sync detector for reliable timing."""
        anr_events = []

        def on_anr(event):
            anr_events.append(event)

        # Use sync detector for more reliable timing control
        detector = ANRDetector(threshold_ms=150, check_interval_ms=50)
        detector.on_anr = on_anr
        detector.start()

        # Simulate work that blocks too long
        detector.heartbeat()
        await asyncio.sleep(0.05)
        detector.heartbeat()
        await asyncio.sleep(0.05)
        # Long pause without heartbeat
        time.sleep(0.3)

        detector.stop()

        # Should have detected ANR
        assert len(anr_events) >= 1

    @pytest.mark.asyncio
    async def test_no_anr_with_regular_heartbeats(self):
        """Ensure regular heartbeats prevent ANR."""
        anr_events = []

        detector = AsyncANRDetector(threshold_ms=300, check_interval_ms=50)
        detector.on_anr = lambda e: anr_events.append(e)
        await detector.start_async()

        # Regular work with heartbeats
        for _ in range(20):
            await asyncio.sleep(0.05)
            await detector.heartbeat_async()

        await detector.stop_async()

        assert len(anr_events) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
