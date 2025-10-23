from __future__ import annotations

from typing import Any, Iterator, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text


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

    def render_stream(self, events: Iterator[Any]) -> None:
        final_text: Optional[str] = None

        for event in events:
            etype = getattr(event, "event", "")

            # Content streaming (intermediate and final)
            if etype in ("RunCompleted",):
                final_text = getattr(event, "content", "")

            # Tool call start
            elif etype in ("ToolCallStarted", "RunToolCallStarted"):
                tool = getattr(event, "tool", None)
                name = getattr(tool, "tool_name", None) or getattr(tool, "name", None) or "tool"
                args = (
                    getattr(event, "tool_args", None) or getattr(tool, "tool_args", None) or {}
                )
                summary = self._summarize_args(args if isinstance(args, dict) else {})
                t = Text.from_markup(
                    f"[{self.tool_line_style}]• ToolCall: [{self.tool_name_style}]{name}[/{self.tool_name_style}]({summary})[/]"
                )
                t.justify = "left"
                t.no_wrap = False
                t.overflow = "fold"
                self.console.print(t)

            else:
                pass

        # Final result display
        self.console.print(Markdown(final_text or ""))

    def _summarize_args(self, args: dict[str, Any]) -> str:
        if not args:
            return ""
        # Filter sensitive keys and truncate values
        hidden_keys = {"api_key", "token", "password", "secret"}
        parts: list[str] = []
        for k, v in args.items():
            if k in hidden_keys:
                continue
            sval = str(v)
            if len(sval) > 64:
                sval = sval[:61] + "..."
            parts.append(f"{k}={sval}")
        summary = ", ".join(parts)
        if len(summary) > 100:
            summary = summary[:97] + "..."
        return summary
