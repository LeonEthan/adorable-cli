"""Enhanced input session with prompt-toolkit integration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, PathCompleter, merge_completers
from prompt_toolkit.document import Document
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Regex patterns for context-aware completion
AT_MENTION_RE = re.compile(r"@(?P<path>(?:[^\\s@]|(?<=\\\\)\\s)*)$")
SLASH_COMMAND_RE = re.compile(r"^/(?P<command>[a-z]*)$")

# Available slash commands for completion
COMMANDS = {
    "/help": "Show available commands",
    "/clear": "Clear screen",
    "/stats": "Show session statistics",
    "/exit": "Quit session",
}


class FilePathCompleter(Completer):
    """Activate filesystem completion only when cursor is after '@'."""

    def __init__(self) -> None:
        self.path_completer = PathCompleter(
            expanduser=True,
            min_input_len=0,
            only_directories=False,
        )

    def get_completions(self, document, complete_event):
        """Get file path completions when @ is detected."""
        text = document.text_before_cursor

        # Use regex to detect @path pattern at end of line
        m = AT_MENTION_RE.search(text)
        if not m:
            return  # Not in an @path context

        path_fragment = m.group("path")

        # Unescape the path for PathCompleter (it doesn't understand escape sequences)
        unescaped_fragment = path_fragment.replace("\\ ", " ")

        # Strip trailing backslash if present (user is in the process of typing an escape)
        unescaped_fragment = unescaped_fragment.removesuffix("\\")

        # Create temporary document for the unescaped path fragment
        temp_doc = Document(text=unescaped_fragment, cursor_position=len(unescaped_fragment))

        # Get completions from PathCompleter and use its start_position
        # PathCompleter returns suffix text with start_position=0 (insert at cursor)
        for comp in self.path_completer.get_completions(temp_doc, complete_event):
            # Add trailing / for directories so users can continue navigating
            completed_path = Path(unescaped_fragment + comp.text).expanduser()
            # Re-escape spaces in the completion text for the command line
            completion_text = comp.text.replace(" ", "\\ ")
            if completed_path.is_dir() and not completion_text.endswith("/"):
                completion_text += "/"

            yield Completion(
                text=completion_text,
                start_position=comp.start_position,  # Use PathCompleter's position (usually 0)
                display=comp.display,
                display_meta=comp.display_meta,
            )


class CommandCompleter(Completer):
    """Activate command completion only when line starts with '/'."""

    def get_completions(self, document, _complete_event):
        """Get command completions when / is at the start."""
        text = document.text_before_cursor

        # Use regex to detect /command pattern at start of line
        m = SLASH_COMMAND_RE.match(text)
        if not m:
            return  # Not in a /command context

        command_fragment = m.group("command")

        # Match commands that start with the fragment (case-insensitive)
        for cmd_name, cmd_desc in COMMANDS.items():
            if cmd_name.startswith(command_fragment.lower()):
                yield Completion(
                    text=cmd_name,
                    start_position=-len(command_fragment),  # Fixed position for original document
                    display=cmd_name,
                    display_meta=cmd_desc,
                )


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

        # Style for toolbar
        self.style = Style.from_dict(
            {
                "bottom-toolbar": "noreverse",
                "toolbar-text": "bg:#1e293b #e2e8f0",  # Slate-800 bg, Slate-200 fg
            }
        )

        # Create session
        self.session: PromptSession = PromptSession(
            history=self.history,
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=self.key_bindings,
            multiline=True,  # Enable multiline but control via keybindings
            wrap_lines=True,
            enable_open_in_editor=True,
            search_ignore_case=True,
            completer=merge_completers([CommandCompleter(), FilePathCompleter()]),
            editing_mode=EditingMode.EMACS,
            complete_while_typing=True,
            complete_in_thread=True,
            mouse_support=False,
            bottom_toolbar=self._get_bottom_toolbar(),
            style=self.style,
            reserve_space_for_menu=5,
        )

    def _create_key_bindings(self) -> KeyBindings:
        """Create custom key bindings - minimal and clear"""
        kb = KeyBindings()

        @kb.add("enter")
        def _(event):
            """Enter submits the input, unless completion menu is active."""
            buffer = event.current_buffer

            # If completion menu is showing, apply the current completion
            if buffer.complete_state:
                current_completion = buffer.complete_state.current_completion
                if not current_completion and buffer.complete_state.completions:
                    buffer.complete_next()
                    buffer.apply_completion(buffer.complete_state.current_completion)
                elif current_completion:
                    buffer.apply_completion(current_completion)
                else:
                    buffer.complete_state = None
            elif buffer.text.strip():
                buffer.validate_and_handle()

        @kb.add("escape", "enter")
        def _(event):
            """Alt+Enter inserts a newline for multi-line input."""
            event.current_buffer.insert_text("\n")

        @kb.add("c-j")
        def _(event):
            """Ctrl+J also inserts newline for multi-line input"""
            event.current_buffer.insert_text("\n")

        @kb.add("c-q")
        def _(event):
            """Quick exit"""
            event.app.exit(exception=KeyboardInterrupt)

        # Backspace handler to retrigger completions after deletion
        @kb.add("backspace")
        def _(event):
            """Handle backspace and retrigger completion if in @ or / context."""
            buffer = event.current_buffer
            buffer.delete_before_cursor(count=1)

            text = buffer.document.text_before_cursor
            if AT_MENTION_RE.search(text) or SLASH_COMMAND_RE.match(text):
                buffer.start_completion(select_first=False)

        return kb

    def _get_bottom_toolbar(self) -> Callable[[], list[tuple[str, str]]]:
        """Return toolbar function."""

        def toolbar() -> list[tuple[str, str]]:
            return [
                (
                    "class:toolbar-text",
                    " Enter: Submit | Alt+Enter/Ctrl+J: Newline | @: File | /: Command ",
                ),
            ]

        return toolbar

    async def prompt_user(self, prompt_text: str = "> ") -> str:
        """Enhanced user input prompt"""
        try:
            user_input = await self.session.prompt_async(
                HTML(f"<style fg='#10b981'>{prompt_text}</style>")
            )
            return user_input.strip()
        except KeyboardInterrupt:
            self.console.print("[info]Use Ctrl+D or type 'exit' to quit[/info]")
            return ""
        except EOFError:
            return "exit"

    def show_quick_help(self):
        """Show minimal, discoverable help for input shortcuts"""
        help_text = """
[header]Input Shortcuts[/header]

[tip]Basic:[/tip]
• [info]Enter[/info] - Submit your message
• [info]Alt+Enter[/info] or [info]Ctrl+J[/info] - Insert newline
• [info]Ctrl+D[/info] or 'exit' - Quit

[tip]Completion:[/tip]
• [info]@[/info] - Trigger file path completion
• [info]/[/info] - Trigger command completion

[tip]History:[/tip]
• [info]↑/↓[/info] - Browse previous messages
• [info]Ctrl+R[/info] - Search command history
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
