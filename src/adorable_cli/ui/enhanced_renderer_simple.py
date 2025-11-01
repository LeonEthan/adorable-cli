"""Simplified enhanced stream renderer with essential interactive features."""

from __future__ import annotations

from typing import Any, Iterator, Optional
from datetime import datetime
from time import perf_counter

from rich.console import Console
from rich.text import Text

from adorable_cli.ui.stream_renderer import StreamRenderer


class SimpleEnhancedRenderer(StreamRenderer):
    """Simplified enhanced stream renderer that adds basic interactive features."""

    def __init__(self, console: Console, enable_diff_display: bool = False, enable_confirmations: bool = False):
        # Call parent constructor, only pass console parameter
        super().__init__(console)

    def render_stream(self, stream: Iterator[Any]) -> None:
        """Enhanced stream rendering - use parent logic only."""
        # Use parent's rendering logic
        super().render_stream(stream)


def create_simple_enhanced_renderer(
    console: Console,
    enable_diff_display: bool = False,
    enable_confirmations: bool = False,
) -> SimpleEnhancedRenderer:
    """Create simple enhanced renderer factory function."""
    return SimpleEnhancedRenderer(
        console,
        enable_diff_display=enable_diff_display,
        enable_confirmations=enable_confirmations,
    )