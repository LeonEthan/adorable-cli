"""ANR (Application Not Responding) detection for the agent loop.

Claude Code's ANR detection system:
- Worker thread monitors main event loop via heartbeat pings
- Threshold: 5000ms default
- Captures stack trace when triggered
- Communicates via thread-safe events

Usage:
    detector = ANRDetector(threshold_ms=5000)
    detector.start()

    # In your main loop, call heartbeat periodically
    detector.heartbeat()

    # When ANR is detected, handler is called
    detector.stop()
"""

from __future__ import annotations

import asyncio
import faulthandler
import io
import signal
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class ANRStatus(Enum):
    """Status of the ANR detector."""

    IDLE = "idle"
    RUNNING = "running"
    TRIGGERED = "triggered"
    STOPPED = "stopped"


@dataclass
class ANREvent:
    """Event fired when ANR is detected."""

    timestamp: float
    last_heartbeat: float
    elapsed_ms: float
    threshold_ms: float
    stack_trace: str
    thread_dump: str


class ANRDetector:
    """Detects when the main event loop becomes unresponsive.

    Uses a monitoring thread that checks for heartbeats from the main thread.
    If no heartbeat is received within the threshold, an ANR is triggered.

    Example:
        detector = ANRDetector(threshold_ms=5000)
        detector.on_anr = lambda event: print(f"ANR! {event.stack_trace}")
        detector.start()

        # Main loop
        while running:
            detector.heartbeat()  # Signal that we're still responsive
            await process_work()

        detector.stop()
    """

    def __init__(
        self,
        threshold_ms: float = 5000,
        check_interval_ms: float = 100,
        on_anr: Optional[Callable[[ANREvent], None]] = None,
        enable_stack_dump: bool = True,
    ):
        """Initialize ANR detector.

        Args:
            threshold_ms: Time without heartbeat before ANR is triggered (default: 5000)
            check_interval_ms: How often to check for heartbeats (default: 100)
            on_anr: Callback when ANR is detected
            enable_stack_dump: Whether to capture full stack dump
        """
        self.threshold_ms = threshold_ms
        self.check_interval_ms = check_interval_ms
        self.on_anr = on_anr
        self.enable_stack_dump = enable_stack_dump

        self._status = ANRStatus.IDLE
        self._last_heartbeat = 0.0
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # For async integration
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._anr_queue: asyncio.Queue[ANREvent] | None = None

    def start(self) -> None:
        """Start the ANR detector."""
        if self._status == ANRStatus.RUNNING:
            return

        with self._lock:
            self._status = ANRStatus.RUNNING
            self._last_heartbeat = time.time() * 1000
            self._stop_event.clear()

        # Start monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="ANRMonitor",
            daemon=True,
        )
        self._monitor_thread.start()

    def stop(self) -> None:
        """Stop the ANR detector."""
        with self._lock:
            self._status = ANRStatus.STOPPED

        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

    def heartbeat(self) -> None:
        """Signal that the main thread is still responsive.

        Call this periodically from the main event loop.
        """
        with self._lock:
            self._last_heartbeat = time.time() * 1000

    def is_responsive(self) -> bool:
        """Check if the system is currently responsive."""
        with self._lock:
            elapsed = (time.time() * 1000) - self._last_heartbeat
            return elapsed < self.threshold_ms

    @property
    def status(self) -> ANRStatus:
        """Current status of the detector."""
        with self._lock:
            return self._status

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in separate thread."""
        while not self._stop_event.is_set():
            time.sleep(self.check_interval_ms / 1000)

            with self._lock:
                if self._status != ANRStatus.RUNNING:
                    continue

                now = time.time() * 1000
                elapsed = now - self._last_heartbeat

                if elapsed > self.threshold_ms:
                    self._status = ANRStatus.TRIGGERED
                    self._trigger_anr(now, elapsed)

    def _trigger_anr(self, timestamp: float, elapsed_ms: float) -> None:
        """Trigger ANR event with stack capture."""
        # Capture stack trace of main thread
        stack_trace = self._capture_stack_trace()
        thread_dump = self._capture_thread_dump() if self.enable_stack_dump else ""

        event = ANREvent(
            timestamp=timestamp / 1000,
            last_heartbeat=self._last_heartbeat / 1000,
            elapsed_ms=elapsed_ms,
            threshold_ms=self.threshold_ms,
            stack_trace=stack_trace,
            thread_dump=thread_dump,
        )

        # Call handler if set
        if self.on_anr:
            try:
                self.on_anr(event)
            except Exception:
                pass  # Don't let ANR handler crash the monitor

    def _capture_stack_trace(self) -> str:
        """Capture stack trace of the main thread."""
        # Get the main thread
        main_thread = None
        for thread_id, frame in sys._current_frames().items():
            if thread_id == threading.main_thread().ident:
                main_thread = frame
                break

        if main_thread is None:
            return "Main thread not found"

        # Format stack trace
        buf = io.StringIO()
        traceback.print_stack(main_thread, file=buf)
        return buf.getvalue()

    def _capture_thread_dump(self) -> str:
        """Capture dump of all threads."""
        buf = io.StringIO()
        buf.write("\n=== Thread Dump ===\n\n")

        frames = sys._current_frames()
        for thread_id, frame in sorted(frames.items()):
            thread_name = "unknown"
            for t in threading.enumerate():
                if t.ident == thread_id:
                    thread_name = t.name
                    break

            buf.write(f"Thread {thread_id} ({thread_name}):\n")
            traceback.print_stack(frame, file=buf)
            buf.write("\n")

        return buf.getvalue()


class AsyncANRDetector(ANRDetector):
    """ANR detector with async/await integration.

    Allows async handlers and integration with asyncio event loops.

    Example:
        detector = AsyncANRDetector(threshold_ms=5000)

        @detector.anr_handler
        async def handle_anr(event):
            print(f"ANR detected: {event.elapsed_ms}ms")
            await notify_user_of_anr(event)

        await detector.start_async()

        # Main loop
        while running:
            await detector.heartbeat_async()
            await process_work()

        await detector.stop_async()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._async_handler: Optional[Callable[[ANREvent], asyncio.Future]] = None
        self._anr_queue: asyncio.Queue[ANREvent] = asyncio.Queue()

    async def start_async(self) -> None:
        """Start the detector with async integration."""
        self._async_loop = asyncio.get_running_loop()

        # Set up sync handler that queues to async
        self.on_anr = self._queue_anr_event

        self.start()

        # Start async event processor
        asyncio.create_task(self._process_anr_events())

    async def stop_async(self) -> None:
        """Stop the detector with async cleanup."""
        self.stop()

    async def heartbeat_async(self) -> None:
        """Async heartbeat method."""
        self.heartbeat()

    def _queue_anr_event(self, event: ANREvent) -> None:
        """Queue ANR event for async processing."""
        if self._async_loop and self._async_loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._anr_queue.put(event),
                    self._async_loop,
                )
            except Exception:
                pass

    async def _process_anr_events(self) -> None:
        """Process ANR events asynchronously."""
        while self.status in (ANRStatus.RUNNING, ANRStatus.TRIGGERED):
            try:
                # Wait for ANR event with timeout
                event = await asyncio.wait_for(
                    self._anr_queue.get(),
                    timeout=1.0,
                )

                # Call async handler if set
                if self._async_handler:
                    try:
                        await self._async_handler(event)
                    except Exception:
                        pass  # Don't crash the processor

            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    def anr_handler(
        self,
        handler: Callable[[ANREvent], asyncio.Future],
    ) -> Callable[[ANREvent], asyncio.Future]:
        """Decorator to set async ANR handler.

        Example:
            @detector.anr_handler
            async def my_handler(event):
                print(f"ANR: {event.elapsed_ms}ms")
        """
        self._async_handler = handler
        return handler


def install_anr_handler(
    threshold_ms: float = 5000,
    callback: Optional[Callable[[ANREvent], None]] = None,
) -> ANRDetector:
    """Install ANR detection with default settings.

    Convenience function for quick setup.

    Args:
        threshold_ms: ANR threshold in milliseconds
        callback: Optional callback for ANR events

    Returns:
        Configured and started ANRDetector
    """
    detector = ANRDetector(
        threshold_ms=threshold_ms,
        on_anr=callback or _default_anr_handler,
    )
    detector.start()
    return detector


def _default_anr_handler(event: ANREvent) -> None:
    """Default ANR handler that prints to stderr."""
    import sys

    print(
        f"\n[ANR DETECTED] Event loop unresponsive for {event.elapsed_ms:.0f}ms "
        f"(threshold: {event.threshold_ms:.0f}ms)\n",
        file=sys.stderr,
    )

    if event.stack_trace:
        print("Stack trace of main thread:", file=sys.stderr)
        print(event.stack_trace, file=sys.stderr)


# Integration with AgentLoop


class AgentLoopANRIntegration:
    """Integration between AgentLoop and ANR detection.

    Automatically sends heartbeats during loop operation and handles
    ANR events appropriately.

    Example:
        integration = AgentLoopANRIntegration(loop, threshold_ms=5000)
        integration.start()

        # ANR detection now active during loop execution
        async for event in loop.run(user_input):
            # Heartbeats sent automatically
            pass

        integration.stop()
    """

    def __init__(
        self,
        loop: Any,
        threshold_ms: float = 5000,
        on_anr: Optional[Callable[[ANREvent], None]] = None,
    ):
        """Initialize integration.

        Args:
            loop: AgentLoop instance
            threshold_ms: ANR threshold
            on_anr: Custom ANR handler (optional)
        """
        self.agent_loop = loop
        self.detector = AsyncANRDetector(
            threshold_ms=threshold_ms,
            enable_stack_dump=True,
        )

        if on_anr:
            self.detector.on_anr = on_anr
        else:
            self.detector.on_anr = self._default_loop_anr_handler

    def start(self) -> None:
        """Start ANR detection."""
        # Create async task to start detector
        try:
            asyncio.create_task(self.detector.start_async())
        except RuntimeError:
            # Not in async context, use sync start
            self.detector.start()

    def stop(self) -> None:
        """Stop ANR detection."""
        self.detector.stop()

    def heartbeat(self) -> None:
        """Manual heartbeat - call from loop phases."""
        self.detector.heartbeat()

    def _default_loop_anr_handler(self, event: ANREvent) -> None:
        """Default handler for AgentLoop ANR events."""
        import logging

        logger = logging.getLogger("adorable.anr")
        logger.error(
            f"ANR detected in AgentLoop: {event.elapsed_ms:.0f}ms "
            f"(threshold: {event.threshold_ms:.0f}ms)"
        )
        logger.error(f"Last heartbeat: {event.last_heartbeat}")
        logger.error(f"Stack trace:\n{event.stack_trace}")

        # Could also:
        # - Emit ANR event to UI
        # - Cancel current operation
        # - Restart the loop
        # - Send telemetry


# Signal-based emergency dump (Unix only)


def enable_emergency_dump(signal_num: int = signal.SIGUSR1) -> None:
    """Enable emergency thread dump on signal (Unix only).

    Sends full thread dump to stderr when signal is received.
    Useful for debugging hung processes.

    Args:
        signal_num: Signal to trigger dump (default: SIGUSR1)
    """
    if sys.platform == "win32":
        return  # Not supported on Windows

    def dump_handler(signum, frame):
        print("\n=== EMERGENCY THREAD DUMP ===\n", file=sys.stderr)

        # Enable faulthandler for full dump
        faulthandler.dump_traceback()

        print("\n=== END THREAD DUMP ===\n", file=sys.stderr)

    signal.signal(signal_num, dump_handler)
