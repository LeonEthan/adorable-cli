"""Enhanced input session with prompt-toolkit integration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class EnhancedInputSession:
    """Enhanced input session based on prompt-toolkit"""

    def __init__(self, console: Console, history_file: Optional[Path] = None):
        self.console = console

        # History
        if history_file is None:
            history_file = Path.home() / ".adorable" / "input_history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = FileHistory(str(history_file))

        # Key bindings
        self.key_bindings = self._create_key_bindings()

        # Default style for prompt sessions
        self.style = None

        # Create session - default single-line mode, Enter to submit
        self.session: PromptSession = PromptSession(
            history=self.history,
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=self.key_bindings,
            multiline=False,  # Single-line mode, Enter to submit
            wrap_lines=True,
            enable_open_in_editor=True,
            search_ignore_case=True,
        )

    def _create_key_bindings(self) -> KeyBindings:
        """Create custom key bindings - minimal and clear"""
        kb = KeyBindings()

        @kb.add("c-q")
        def _(event):
            """Quick exit"""
            event.app.exit(exception=KeyboardInterrupt)

        @kb.add("c-j")
        def _(event):
            """Insert newline for multiline input"""
            buffer = event.app.current_buffer
            buffer.insert_text("\n")

        return kb

    def prompt_user(self, prompt_text: str = "> ") -> str:
        """Enhanced user input prompt"""
        try:
            # Get user input, keeping only history suggestions
            user_input = self.session.prompt(prompt_text)
            return user_input.strip()
        except KeyboardInterrupt:
            self.console.print("[info]Use Ctrl+D or type 'exit' to quit[/info]")
            return ""
        except EOFError:
            return "exit"

    def get_multiline_input(self, prompt_text: str = "> ") -> str:
        """Get multiline input (for code blocks, etc.)"""
        return self.session.prompt(prompt_text, multiline=True).strip()

    def show_quick_help(self):
        """Show minimal, discoverable help for input shortcuts"""
        help_text = """
[header]Input Shortcuts[/header]

[tip]Basic:[/tip]
• [info]Enter[/info] - Submit your message
• [info]Ctrl+J[/info] - Insert newline (multi-line input)
• [info]Ctrl+D[/info] or 'exit' - Quit

[tip]History:[/tip]
• [info]↑/↓[/info] - Browse previous messages
• [info]Ctrl+R[/info] - Search command history

[tip]More Commands:[/tip]
• Type [info]/help[/info] for all available commands
        """
        self.console.print(
            Panel(
                help_text,
                title=Text("Input Help", style="panel_title"),
                border_style="panel_border",
                padding=(0, 1),
            )
        )


def create_enhanced_session(console: Console) -> EnhancedInputSession:
    """Factory function to create enhanced input session"""
    return EnhancedInputSession(console)
