from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any, Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text

from adorable_cli.ui.utils import summarize_args


class StreamRenderer:
    """
    Streaming renderer for agent responses.

    Design:
    - Shows a spinner while waiting for content (Thinking...)
    - When content arrives: stops spinner, streams content using Live display (Markdown)
    - Tool calls: pauses content stream, prints tool call, resumes spinner
    - Final content: built incrementally
    """

    def __init__(
        self,
        console: Console,
        *,
        tool_line_style: str = "tool_line",
        tool_name_style: str = "tool_name",
        header_style: str = "header",
    ) -> None:
        self.console = console
        self.tool_line_style = tool_line_style
        self.tool_name_style = tool_name_style
        self.header_style = header_style

        # Stream state
        self.spinner: Optional[Live] = None
        self.content_live: Optional[Live] = None
        self.segment_content = ""  # Content since last interruption
        self.full_content = ""  # Total accumulated content

    def start_stream(self) -> None:
        """Initialize state and show thinking spinner."""
        self.segment_content = ""
        self.full_content = ""
        self._start_spinner()

    def _start_spinner(self) -> None:
        """Start the thinking spinner."""
        # Only start spinner if we are not currently streaming content
        if self.content_live is None and self.spinner is None:
            self.spinner = Live(
                Spinner("dots", text="Thinking...", style="dim"),
                console=self.console,
                transient=True,
            )
            self.spinner.start()

    def _stop_spinner(self) -> None:
        """Stop the thinking spinner."""
        if self.spinner is not None:
            self.spinner.stop()
            self.spinner = None

    def update_content(self, delta: str) -> None:
        """Handle incoming content delta."""
        if not delta:
            return

        # Stop spinner if it's running
        self._stop_spinner()

        self.segment_content += delta
        self.full_content += delta

        # Start content live display if not running
        if self.content_live is None:
            self.content_live = Live(
                Markdown(self.segment_content),
                console=self.console,
                transient=False,  # Content should persist
                refresh_per_second=10,
            )
            self.content_live.start()
        else:
            self.content_live.update(Markdown(self.segment_content))

    def set_final_content(self, content: str) -> None:
        """Set the final content (fallback/update)."""
        if content and len(content) > len(self.full_content):
            # If we missed something, append it?
            # Or just update full_content for get_final_text
            self.full_content = content

    def render_tool_call(self, event: Any) -> None:
        """Render tool call event line."""
        etype = getattr(event, "event", "")
        if etype not in ("ToolCallStarted", "RunToolCallStarted"):
            return

        tool = getattr(event, "tool", None)
        name = getattr(tool, "tool_name", None) or getattr(tool, "name", None) or "tool"
        args = getattr(event, "tool_args", None) or getattr(tool, "tool_args", None) or {}
        summary = summarize_args(args if isinstance(args, dict) else {})

        # Stop any active display
        self._stop_spinner()
        if self.content_live is not None:
            self.content_live.stop()
            self.content_live = None
            self.segment_content = ""  # Reset segment for next text block

        # Print tool call
        t = Text.from_markup(
            f"[{self.tool_line_style}]• ToolCall: [{self.tool_name_style}]{name}[/{self.tool_name_style}]({summary})[/]"
        )
        self.console.print(t)

        # Resume spinner for next operation
        self._start_spinner()

    def pause_stream(self) -> None:
        """Pause for user interaction."""
        self._stop_spinner()
        if self.content_live is not None:
            self.content_live.stop()
            self.content_live = None
            # Do NOT reset segment_content here?
            # If we pause, we might resume adding to the same segment?
            # But render_tool_call usually happens before pause (if tool needs confirmation).
            # If we pause for tool confirmation, render_tool_call has likely already been called.
            # So segment_content is likely empty.

    def resume_stream(self) -> None:
        """Resume after interaction."""
        self._start_spinner()

    def finish_stream(self) -> None:
        """Finalize: stop all displays."""
        self._stop_spinner()
        if self.content_live is not None:
            self.content_live.stop()
            self.content_live = None

        # Ensure final newline if needed?
        # Live(transient=False) usually leaves a newline.

    def get_final_text(self) -> str:
        """Get final text."""
        return self.full_content

    def handle_event(self, event: Any) -> None:
        """Legacy method."""
        self.render_tool_call(event)

    def render_footer(self, final_metrics: Any, start_at: datetime, start_perf: float) -> None:
        duration_val = getattr(final_metrics, "duration", None) if final_metrics else None
        if not isinstance(duration_val, (int, float)):
            duration_val = perf_counter() - start_perf

        self.console.print(
            Text(f"Completed at {start_at:%H:%M:%S} • {duration_val:.2f}s", style="muted")
        )
