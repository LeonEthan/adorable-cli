from __future__ import annotations

from typing import Any, Iterator, Optional
from datetime import datetime
from time import perf_counter

from rich.console import Console
from rich.markdown import Markdown
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
        tool_line_style: str = "cyan",
        tool_name_style: str = "magenta",
    ) -> None:
        self.console = console
        self.tool_line_style = tool_line_style
        self.tool_name_style = tool_name_style

    def render_stream(self, stream: Iterator[Any]) -> None:
        final_text: Optional[str] = None
        final_metrics: Optional[Any] = None
        start_at = datetime.now()
        start_perf = perf_counter()

        for event in stream:
            etype = getattr(event, "event", "")

            # Content streaming (intermediate and final)
            if etype in ("RunCompleted",):
                final_text = getattr(event, "content", "")
                final_metrics = getattr(event, "metrics", None)

            # Tool call start
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

        # Final result display
        self.console.print(Text("🐱 Adorable:", style="bold orange3"))
        self.console.print(Markdown(final_text or ""))

        # Session footer: time and tokens
        # duration: prefer metrics.duration; fallback to local perf counter
        duration_val = None
        if final_metrics is not None:
            duration_val = getattr(final_metrics, "duration", None)
        if not isinstance(duration_val, (int, float)):
            duration_val = perf_counter() - start_perf
        time_line = Text(
            f"⌛ {start_at:%Y-%m-%d %H:%M:%S} • elapsed {duration_val:.2f}s",
            style="grey58",
        )
        self.console.print(time_line)

        # tokens: show if available; graceful degrade otherwise
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
                style="grey58",
            )
            self.console.print(tokens_line)

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
