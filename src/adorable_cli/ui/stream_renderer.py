from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any

from rich.console import Console
from rich.text import Text

from adorable_cli.ui.utils import summarize_args


class StreamRenderer:
    """
    Event-driven stream renderer for Agno Agent responses.

    - Streams content as it arrives, rendering Markdown with light beautification.
    - Shows tool call basic info in Claude Code style: `* tool call ...`.
    - Hides reasoning-related details entirely.
    - Produces a final, beautified result panel at the end.
    """

    def __init__(
        self,
        console: Console,
        *,
        tool_line_style: str = "tool_line",
        tool_name_style: str = "tool_name",
    ) -> None:
        self.console = console
        self.tool_line_style = tool_line_style
        self.tool_name_style = tool_name_style

    def handle_event(self, event: Any) -> None:
        """Render specific event lines in a consistent style without consuming streams.

        Currently used for ToolCall line rendering to de-duplicate presentation between
        main process and renderer. Keeps pause/confirmation logic in the main flow.
        """
        etype = getattr(event, "event", "")
        if etype in ("ToolCallStarted", "RunToolCallStarted"):
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

    def render_footer(self, final_metrics: Any, start_at: datetime, start_perf: float) -> None:
        duration_val = None
        if final_metrics is not None:
            duration_val = getattr(final_metrics, "duration", None)
        if not isinstance(duration_val, (int, float)):
            duration_val = perf_counter() - start_perf
        time_line = Text(
            f"⌛ {start_at:%Y-%m-%d %H:%M:%S} • elapsed {duration_val:.2f}s",
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
                f"🔢 Tokens: input {input_tokens if input_tokens is not None else '?'} • output {output_tokens if output_tokens is not None else '?'} • total {total_tokens if total_tokens is not None else '?'}",
                style="muted",
            )
            self.console.print(tokens_line)
