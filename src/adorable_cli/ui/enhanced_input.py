"""Enhanced input session with prompt-toolkit integration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console


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
        """Create custom key bindings"""
        kb = KeyBindings()

        @kb.add("c-q")
        def _(event):
            """Quick exit"""
            event.app.exit(exception=KeyboardInterrupt)

        @kb.add("c-j")  # Ctrl+J: New line
        def _(event):
            """Ctrl+J: New line"""
            buffer = event.app.current_buffer
            buffer.insert_text("\n")

        @kb.add("f1")  # F1 for manual multiline input
        def _(event):
            """F1: Manual multiline input mode"""
            # Create temporary multiline input session
            buffer = event.app.current_buffer
            current_text = buffer.text

            # Use prompt_toolkit's prompt function for multiline input
            from prompt_toolkit import prompt

            multiline_input = prompt(
                "Multiline input (Ctrl+D to finish): ",
                multiline=True,
                default=current_text,
                key_bindings=self.key_bindings,
                style=self.style,
            )

            # Set multiline input content back to original buffer
            buffer.text = multiline_input
            buffer.cursor_position = len(multiline_input)

        @kb.add("f3")
        def _(event):
            """F3: Switch to multiline mode for complex input"""
            buffer = event.app.current_buffer

            # Temporarily switch to multiline mode
            from prompt_toolkit import prompt

            multiline_input = prompt(
                "Multiline editing mode (Esc+Enter to exit): ",
                multiline=True,
                default=buffer.text,
                key_bindings=self.key_bindings,
                style=self.style,
            )

            buffer.text = multiline_input
            buffer.cursor_position = len(multiline_input)

        return kb

    def prompt_user(self, prompt_text: str = "> ") -> str:
        """Enhanced user input prompt"""
        try:
            # Get user input, keeping only history suggestions
            user_input = self.session.prompt(prompt_text)
            return user_input.strip()
        except KeyboardInterrupt:
            self.console.print("[yellow]👋 Use Ctrl+D or type 'exit' to quit[/yellow]")
            return ""
        except EOFError:
            return "exit"

    def get_multiline_input(self, prompt_text: str = "> ") -> str:
        """Get multiline input (for code blocks, etc.)"""
        return self.session.prompt(prompt_text, multiline=True).strip()

    def show_quick_help(self):
        """Show quick help"""
        help_text = """
[bold cyan]🚀 Adorable CLI Enhanced Input Features[/bold cyan]

[yellow]Input Modes:[/yellow]
• [cyan]Enter[/cyan] - Submit input (default behavior)
• [cyan]Ctrl+J[/cyan] - New line
• [cyan]F1[/cyan] - Manual multiline input mode
• [cyan]F3[/cyan] - Complex multiline editing mode

[yellow]Shortcuts:[/yellow]
• [cyan]Ctrl+Q[/cyan] - Quick exit
• [cyan]Ctrl+R[/cyan] - Search command history
• [cyan]↑/↓[/cyan] - Browse command history

[yellow]History Features:[/yellow]
• Command history recording and auto-save
• Automatic command history suggestions and completion
• Support for history search functionality
        """
        self.console.print(help_text)


def create_enhanced_session(console: Console) -> EnhancedInputSession:
    """Factory function to create enhanced input session"""
    return EnhancedInputSession(console)
