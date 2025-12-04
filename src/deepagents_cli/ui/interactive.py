import os
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from time import perf_counter
from typing import Any

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text

from deepagents_cli.console import console
from deepagents_cli.ui.enhanced_input import create_enhanced_session
from deepagents_cli.ui.stream_renderer import StreamRenderer
from deepagents_cli.ui.utils import detect_language_from_extension, summarize_args


def print_version() -> int:
    try:
        ver = pkg_version("deepagents-cli")
        print(f"deepagents-cli {ver}")
    except PackageNotFoundError:
        # Fallback when distribution metadata is unavailable (e.g., dev runs)
        print("deepagents-cli (version unknown)")
    return 0


def _get_shell_text(targs: dict) -> str:
    """Normalize shell tool args to a single command text for checks/preview."""
    val = targs.get("command", None)
    if val is None:
        val = targs.get("args", None) or targs.get("argv", None)
    if isinstance(val, (list, tuple)):
        return " ".join(str(x) for x in val)
    return str(val or "")


def handle_special_command(user_input: str, enhanced_session, console: Console, agent) -> bool:
    """Handle special commands with / prefix. Returns True if command was handled.

    Supports unified / prefix commands:
    - /help - Show available commands
    - /clear - Clear screen
    - /stats - Session statistics
    - /auto, /normal - Change confirmation mode
    - /exit - Quit session

    Maintains backward compatibility with legacy commands.
    """
    cmd = user_input.strip().lower()

    # Exit commands (support both formats)
    exit_on = ["exit", "exit()", "quit", "q", "bye", "/exit", "/quit", "/q"]
    if cmd in exit_on:
        console.print("Bye!", style="info")
        return True

    # /help - Show all available commands
    if cmd in ["/help", "help", "/?"]:  # Backward compat: help
        _show_commands_help(console)
        return True

    # /clear - Clear screen
    if cmd in ["/clear", "/cls", "clear", "cls"]:  # Backward compat: clear, cls
        console.clear()
        console.print("[muted]Screen cleared. Type /help for commands.[/muted]")
        return True

    # /stats - Session statistics
    if cmd in ["/stats", "session-stats"]:  # Backward compat: session-stats
        _show_session_stats(console)
        return True

    # Legacy: help-input (show input help)
    if cmd == "help-input":
        enhanced_session.show_quick_help()
        return True

    # Legacy: enhanced-mode (deprecated, redirect to /help)
    if cmd == "enhanced-mode":
        console.print("[warning]'enhanced-mode' is deprecated. Use '/help' instead.[/warning]")
        _show_commands_help(console)
        return True

    return False


def _show_commands_help(console: Console) -> None:
    """Show all available special commands."""
    help_text = """
[header]Available Commands[/header]

[tip]Session:[/tip]
• [info]/help[/info] - Show this help
• [info]/clear[/info] - Clear screen
• [info]/stats[/info] - Show session statistics
• [info]/exit[/info] or type 'exit' - Quit

[tip]Input Help:[/tip]
• Type 'help-input' - Input shortcuts and history

[muted]Tip: Most commands work with or without / prefix[/muted]
    """

    console.print(
        Panel(
            help_text,
            title=Text("DeepAgents CLI", style="panel_title"),
            border_style="panel_border",
            padding=(0, 1),
        )
    )


def _show_session_stats(console: Console) -> None:
    """Show current session statistics."""
    stats_text = """[tip]Session Status[/tip]

• Enhanced Input: [success]Enabled[/success]
• History: Auto-complete & search
• Multiline: Ctrl+J / Alt+Enter"""

    console.print(
        Panel(
            stats_text,
            title=Text("Session", style="panel_title"),
            border_style="panel_border",
            padding=(0, 1),
        )
    )


def handle_tool_confirmation(tool, console: Console) -> bool:
    """Show tool preview and get user confirmation. Returns True if confirmed."""
    tname = getattr(tool, "tool_name", None) or getattr(tool, "name", None) or "tool"
    targs = getattr(tool, "tool_args", None) or {}

    # Hard bans: block dangerous system-level commands regardless of mode
    if tname == "run_shell_command":
        cmd_text = _get_shell_text(targs)
        lower = cmd_text.lower().strip()
        if "rm -rf /" in lower:
            console.print(Text.from_markup("[error]Blocked dangerous command (hard-ban)[/error]"))
            return False
        if lower.startswith("sudo ") or " sudo " in lower:
            console.print(Text.from_markup("[error]Blocked dangerous command (hard-ban)[/error]"))
            return False

    # Auto mode logic is handled in main_agent.py by setting requires_confirmation=False
    # If we are here, it means requires_confirmation=True, so we must ask.

    # Normal mode: show detailed preview and ask for confirmation
    preview_group = []
    header_text = Text(f"Tool: {tname}", style="tool_name")
    preview_group.append(header_text)

    try:
        if tname == "execute_python_code":
            code = str(targs.get("code", ""))
            code_display = code if len(code) <= 2000 else (code[:1970] + "...")
            preview_group.append(
                Syntax(code_display, "python", theme="monokai", line_numbers=False)
            )
        elif tname == "run_shell_command":
            cmd = _get_shell_text(targs)
            cmd_display = cmd if len(cmd) <= 1000 else (cmd[:970] + "...")
            preview_group.append(Syntax(cmd_display, "bash", theme="monokai", line_numbers=False))
        elif tname == "save_file":
            file_path = str(
                targs.get("file_path")
                or targs.get("path")
                or targs.get("file_name")
                or targs.get("filename")
                or ""
            )
            content = str(
                targs.get("content")
                or targs.get("contents")
                or targs.get("text")
                or targs.get("data")
                or targs.get("body")
                or ""
            )
            content_display = content if len(content) <= 2000 else (content[:1970] + "...")
            info = (
                Text(f"Save path: {file_path}", style="info")
                if file_path
                else Text("Save path not provided", style="error")
            )
            preview_group.append(info)
            if content_display:
                lang = detect_language_from_extension(file_path)
                if lang:
                    preview_group.append(
                        Syntax(
                            content_display,
                            lang,
                            theme="monokai",
                            line_numbers=False,
                        )
                    )
                else:
                    preview_group.append(Text(content_display))
        else:
            # Generic args preview
            summary = summarize_args(targs if isinstance(targs, dict) else {})
            preview_group.append(Text(f"Args: {summary}", style="info"))
    except Exception:
        pass

    console.print(
        Panel(
            Group(*preview_group),
            title=Text("Tool Call Preview", style="panel_title"),
            border_style="panel_border",
            padding=(0, 1),
        )
    )

    resp = Prompt.ask(
        f"Confirm running tool [tool_name]{tname}[/tool_name]?",
        choices=["y", "n"],
        default="y",
    )
    return resp == "y"


def process_agent_stream(
    agent, user_input: str, renderer: StreamRenderer, console: Console
) -> tuple[str, Any, datetime, float]:
    """Process agent stream with tool confirmations. Returns (final_text, metrics, start_time, start_perf)."""
    final_metrics = None
    start_at = datetime.now()
    start_perf = perf_counter()

    stream = agent.run(user_input, stream=True, stream_intermediate_steps=True)

    # Start streaming with renderer
    renderer.start_stream()

    try:
        while True:
            paused_event = None

            for event in stream:
                etype = getattr(event, "event", "")

                # Handle streaming content
                if etype in ("RunContent", "TeamRunContent"):
                    content = getattr(event, "content", "")
                    if content:
                        renderer.update_content(content)

                if etype in ("RunCompleted", "TeamRunCompleted"):
                    content = getattr(event, "content", "")
                    if content and not renderer.get_final_text():
                        renderer.update_content(content)

                    metrics = getattr(event, "metrics", None)
                    if metrics:
                        final_metrics = metrics

                if etype in ("ToolCallStarted", "RunToolCallStarted"):
                    renderer.render_tool_call(event)

                if getattr(event, "is_paused", False):
                    paused_event = event
                    break

            # Handle paused event for tool confirmations
            if paused_event is not None:
                renderer.pause_stream()

                tools_list = (
                    getattr(paused_event, "tools_requiring_confirmation", None)
                    or getattr(paused_event, "tools", None)
                    or []
                )

                for tool in tools_list:
                    confirmed = handle_tool_confirmation(tool, console)
                    setattr(tool, "confirmed", confirmed)

                stream = agent.continue_run(
                    run_id=getattr(paused_event, "run_id", None),
                    updated_tools=getattr(paused_event, "tools", None),
                    stream=True,
                    stream_intermediate_steps=True,
                )
                renderer.resume_stream()
            else:
                break
    finally:
        # Always finish the stream properly
        renderer.finish_stream()

    final_text = renderer.get_final_text()
    return final_text, final_metrics, start_at, start_perf


def run_interactive(agent) -> int:
    # Get configuration
    try:
        ver = pkg_version("deepagents-cli")
    except PackageNotFoundError:
        ver = "version unknown"
    model_id = os.environ.get("DEEPAGENTS_MODEL_ID", "gpt-5-mini")
    cwd = str(Path.cwd())
    show_cat = os.environ.get("DEEPAGENTS_SHOW_CAT", "true").lower() in ("true", "1", "yes")

    # Claude Code-style welcome UI: two-column layout + optional pixel cat
    if show_cat:
        pixel_sprite = r"""
[cat_primary]      ████          ████      [/cat_primary]
[cat_primary]      ██[/cat_primary][cat_secondary]██[/cat_secondary][cat_primary]██      ██[/cat_primary][cat_secondary]██[/cat_secondary][cat_primary]██[/cat_primary]
[cat_primary]      ██[/cat_primary][cat_secondary]████[/cat_secondary][cat_primary]██████[/cat_primary][cat_secondary]████[/cat_secondary][cat_primary]██[/cat_primary]
[cat_primary]    ██[/cat_primary][cat_secondary]██████████████████[/cat_secondary][cat_primary]██[/cat_primary]
[cat_primary]    ██[/cat_primary][cat_secondary]████[/cat_secondary][cat_accent]██[/cat_accent][cat_secondary]██████[/cat_secondary][cat_accent]██[/cat_accent][cat_secondary]████[/cat_secondary][cat_primary]██[/cat_primary]
[cat_primary]    ██[/cat_primary][cat_secondary]██████████████████[/cat_secondary][cat_primary]██[/cat_primary]
[cat_primary]    ████[/cat_primary][cat_secondary]██████████████[/cat_secondary][cat_primary]████[/cat_primary]
[cat_primary]        ██████████████[/cat_primary]
"""
        left_group = Group(
            Align.center(Text("Welcome to DeepAgents CLI", style="header")),
            Align.center(Text.from_markup(pixel_sprite)),
        )
    else:
        left_group = Group(
            Align.center(Text("Welcome to DeepAgents CLI", style="header")),
            Align.center(Text(f"\nVersion {ver}", style="info")),
        )

    # Right panel: clean tips layout
    right_group = Group(
        Text("Quick Start", style="tip"),
        Rule(style="rule_light"),
        Text("• Type your question to start", style="muted"),
        Text("• Use /help for all commands", style="muted"),
        Text("• Ctrl+J or Alt+Enter for newline", style="muted"),
        Text("• @ for file completion", style="muted"),
        Text(""),
        Text("Configuration", style="tip"),
        Rule(style="rule_light"),
        Text(f"Model: {model_id}", style="muted"),
        Text(f"Path: {cwd}", style="muted"),
    )

    console.print(
        Panel(
            Columns([left_group, right_group], equal=True, expand=True),
            title=Text("DeepAgents CLI", style="panel_title"),
            border_style="panel_border",
            padding=(0, 1),
        )
    )

    # Create enhanced input session
    enhanced_session = create_enhanced_session(console)

    # Enhanced interaction loop with simplified control flow
    console.print("[success]Ready to assist[/success]")

    # Initialize renderer once for the session
    renderer = StreamRenderer(console)

    while True:
        try:
            # Get user input
            user_input = enhanced_session.prompt_user(">> ")
        except KeyboardInterrupt:
            console.print("Bye!", style="info")
            return 0
        except EOFError:
            console.print("Bye!", style="info")
            break

        if not user_input:
            continue

        # Handle special commands (returns True if command was handled)
        if handle_special_command(user_input, enhanced_session, console, agent):
            # Update local confirm_mode if it was changed
            if user_input.lower() in ["exit", "exit()", "quit", "q", "bye"]:
                break
            continue

        try:
            # Process agent stream with tool confirmations
            final_text, final_metrics, start_at, start_perf = process_agent_stream(
                agent, user_input, renderer, console
            )

            # Display footer with metrics
            renderer.render_footer(final_metrics, start_at, start_perf)
        except Exception:
            console.print_exception()

    return 0
