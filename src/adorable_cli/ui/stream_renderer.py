from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text

from adorable_cli.ui.utils import summarize_args


class StreamRenderer:
    """
    Enhanced stream renderer for Agno Agent responses.

    Manages the complete streaming lifecycle:
    - Live display initialization and updates
    - Streaming content rendering with Markdown
    - Tool call event rendering
    - Pause/resume handling for confirmations
    - Final metrics display
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
        self.live: Optional[Live] = None
        self.final_text = ""
        self.first_content = True

    def start_stream(self) -> None:
        """Initialize Live display for streaming."""
        if self.live is None:
            self.live = Live(console=self.console, refresh_per_second=10, transient=False)
            self.live.start()
        self.final_text = ""
        self.first_content = True

    def update_content(self, content: str) -> None:
        """Append content chunk and update live display."""
        if not content or self.live is None:
            return
        
        # Check if cat should be shown
        import os
        show_cat = os.environ.get("DEEPAGENTS_SHOW_CAT", "true").lower() in ("true", "1", "yes")
        header_text = "🐱 Adorable:\n" if show_cat else "Adorable:\n"
        
        if self.first_content:
            # First chunk: set up the header
            header = Text(header_text, style=self.header_style)
            self.final_text = content
            self.live.update(Group(header, Markdown(self.final_text)))
            self.first_content = False
        else:
            # Subsequent chunks: append and update
            self.final_text += content
            header = Text(header_text, style=self.header_style)
            self.live.update(Group(header, Markdown(self.final_text)))

    def render_tool_call(self, event: Any) -> None:
        """Render tool call event line.
        
        Pauses live display, prints tool line, then resumes.
        """
        etype = getattr(event, "event", "")
        if etype not in ("ToolCallStarted", "RunToolCallStarted"):
            return
        
        tool = getattr(event, "tool", None)
        name = getattr(tool, "tool_name", None) or getattr(tool, "name", None) or "tool"
        args = getattr(event, "tool_args", None) or getattr(tool, "tool_args", None) or {}
        summary = summarize_args(args if isinstance(args, dict) else {})
        
        t = Text.from_markup(
            f"[{self.tool_line_style}]• ToolCall: [{self.tool_name_style}]{name}[/{self.tool_name_style}]({summary})[/]"
        )
        t.justify = "left"
        t.no_wrap = False
        t.overflow = "fold"
        self.console.print(t)

    def pause_stream(self) -> None:
        """Pause live display for user interaction."""
        if self.live is not None:
            self.live.stop()

    def resume_stream(self) -> None:
        """Resume live display after interaction."""
        if self.live is not None:
            self.live.start()

    def finish_stream(self) -> None:
        """Stop live display and finalize."""
        if self.live is not None:
            self.live.stop()
            self.live = None
    
    def get_final_text(self) -> str:
        """Get the accumulated final text."""
        return self.final_text

    # Legacy method for backward compatibility
    def handle_event(self, event: Any) -> None:
        """Legacy method - use render_tool_call instead."""
        self.render_tool_call(event)

    def render_footer(self, final_metrics: Any, start_at: datetime, start_perf: float) -> None:
        duration_val = None
        if final_metrics is not None:
            duration_val = getattr(final_metrics, "duration", None)
        if not isinstance(duration_val, (int, float)):
            duration_val = perf_counter() - start_perf
        time_line = Text(
            f"Completed at {start_at:%H:%M:%S} • {duration_val:.2f}s",
            style="muted",
        )
        self.console.print(time_line)

        input_tokens = None
        output_tokens = None
        total_tokens = None
        if final_metrics is not None:
            input_tokens = getattr(final_metrics, "input_tokens", None)
            output_tokens = getattr(final_metrics, "output_tokens", None)
            total_tokens = getattr(final_metrics, "total_tokens", None)
        if any(v is not None for v in (input_tokens, output_tokens, total_tokens)):
            tokens_line = Text(
                f"Tokens: in={input_tokens if input_tokens is not None else '?'} out={output_tokens if output_tokens is not None else '?'} total={total_tokens if total_tokens is not None else '?'}",
                style="muted",
            )
            self.console.print(tokens_line)
