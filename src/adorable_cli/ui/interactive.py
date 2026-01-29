import os
import asyncio
import inspect
import types
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, List

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text

from adorable_cli.console import console
from adorable_cli.settings import settings
from adorable_cli.config import CONFIG_PATH
from adorable_cli.ext.commands import CommandsLoader
from adorable_cli.ui.enhanced_input import create_enhanced_session
from adorable_cli.ui.stream_renderer import StreamRenderer
from adorable_cli.ui.utils import detect_language_from_extension, summarize_args


def _is_mcp_tool(obj: Any) -> bool:
    t = type(obj)
    if t.__name__ in {"MCPTools", "MultiMCPTools"}:
        return True
    return t.__module__.startswith("agno.tools.mcp")


async def _pin_mcp_tools_to_current_task(agent: Any) -> list[Any]:
    if os.environ.get("ADORABLE_DISABLE_MCP", "").lower() in {"1", "true", "yes", "on"}:
        return []

    pin_setting = os.environ.get("ADORABLE_MCP_PIN_ON_STARTUP", "").lower()
    if pin_setting in {"0", "false", "no", "off"}:
        return []

    tools = [t for t in getattr(agent, "tools", []) if _is_mcp_tool(t)]
    if not tools:
        return []

    owner_task = asyncio.current_task()
    if owner_task is None:
        return []

    pinned: list[Any] = []

    for tool in tools:
        if getattr(tool, "_adorable_pinned", False):
            pinned.append(tool)
            continue

        if pin_setting in {"1", "true", "yes", "on"} and hasattr(tool, "connect"):
            timeout_s = float(os.environ.get("ADORABLE_MCP_CONNECT_TIMEOUT", "10.0"))
            try:
                await asyncio.wait_for(tool.connect(force=True), timeout=timeout_s)
            except Exception:
                continue

        setattr(tool, "_adorable_owner_task", owner_task)
        setattr(tool, "_adorable_original_close", getattr(tool, "close", None))
        setattr(tool, "_adorable_original_connect", getattr(tool, "connect", None))
        setattr(tool, "_adorable_original_aexit", getattr(tool, "__aexit__", None))

        async def _connect_guard(self, force: bool = False):
            orig = getattr(self, "_adorable_original_connect", None)
            if orig is None:
                return None
            setattr(self, "_adorable_connection_task", asyncio.current_task())
            return await orig(force=force)

        async def _close_guard(self):
            orig = getattr(self, "_adorable_original_close", None)
            if orig is None:
                return None
            conn_task = getattr(self, "_adorable_connection_task", None)
            if conn_task is not None and asyncio.current_task() is not conn_task:
                return None
            return await orig()

        async def _aexit_guard(self, _exc_type, _exc_val, _exc_tb):
            orig = getattr(self, "_adorable_original_aexit", None)
            if orig is None:
                return None
            conn_task = getattr(self, "_adorable_connection_task", None)
            if conn_task is not None and asyncio.current_task() is not conn_task:
                return None
            return await orig(_exc_type, _exc_val, _exc_tb)

        tool.connect = types.MethodType(_connect_guard, tool)
        if hasattr(tool, "close"):
            tool.close = types.MethodType(_close_guard, tool)
        if hasattr(tool, "__aexit__"):
            tool.__aexit__ = types.MethodType(_aexit_guard, tool)

        setattr(tool, "_adorable_pinned", True)
        pinned.append(tool)

    return pinned


async def _close_pinned_mcp_tools(pinned: list[Any]) -> None:
    if not pinned:
        return
    for tool in pinned:
        close = getattr(tool, "close", None)
        if close is None:
            continue
        try:
            await close()
        except Exception:
            continue


def print_version() -> int:
    try:
        ver = pkg_version("adorable-cli")
        print(f"adorable-cli {ver}")
    except PackageNotFoundError:
        # Fallback when distribution metadata is unavailable (e.g., dev runs)
        print("adorable-cli (version unknown)")
    return 0


def _get_shell_text(targs: dict) -> str:
    """Normalize shell tool args to a single command text for checks/preview."""
    val = targs.get("command", None)
    if val is None:
        val = targs.get("args", None) or targs.get("argv", None)
    if isinstance(val, (list, tuple)):
        return " ".join(str(x) for x in val)
    return str(val or "")


def _looks_like_mcp_jsonrpc_error(exc: BaseException) -> bool:
    """Detect MCP JSON-RPC parse errors so we can show a friendly message."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur and id(cur) not in seen:
        seen.add(id(cur))
        text = f"{type(cur).__name__}: {cur}"
        if "Failed to parse JSONRPC message from server" in text:
            return True
        if "JSONRPCMessage" in text and "Invalid JSON" in text:
            return True
        if "json_invalid" in text and "JSONRPCMessage" in text:
            return True
        cur = cur.__cause__ or cur.__context__
    return False


# Command Dispatcher Definition
CommandCallback = Callable[[str, Any, Console, Any], bool]
SPECIAL_COMMANDS: Dict[str, CommandCallback] = {}
EXIT_COMMANDS = ["exit", "exit()", "quit", "q", "bye", "/exit", "/quit", "/q"]


def register_command(aliases: List[str], func: CommandCallback):
    for alias in aliases:
        SPECIAL_COMMANDS[alias] = func


# Command Handlers
def cmd_exit(cmd: str, session, console: Console, agent) -> bool:
    console.print("Bye!", style="info")
    return True


def cmd_help(cmd: str, session, console: Console, agent) -> bool:
    _show_commands_help(console)
    return True


def cmd_clear(cmd: str, session, console: Console, agent) -> bool:
    console.clear()
    console.print("[muted]Screen cleared. Type /help for commands.[/muted]")
    return True


def cmd_stats(cmd: str, session, console: Console, agent) -> bool:
    _show_session_stats(console)
    return True


def cmd_help_input(cmd: str, session, console: Console, agent) -> bool:
    session.show_quick_help()
    return True


def cmd_enhanced_mode(cmd: str, session, console: Console, agent) -> bool:
    console.print("[warning]'enhanced-mode' is deprecated. Use '/help' instead.[/warning]")
    _show_commands_help(console)
    return True


# Register Commands
register_command(EXIT_COMMANDS, cmd_exit)
register_command(["/help", "help", "/?"], cmd_help)
register_command(["/clear", "/cls", "clear", "cls"], cmd_clear)
register_command(["/stats", "session-stats"], cmd_stats)
register_command(["help-input"], cmd_help_input)
register_command(["enhanced-mode"], cmd_enhanced_mode)


def handle_special_command(user_input: str, enhanced_session, console: Console, agent) -> bool:
    """Handle special commands with / prefix using dispatch pattern.
    Returns True if command was handled.
    """
    cmd = user_input.strip().lower()
    if cmd in SPECIAL_COMMANDS:
        return SPECIAL_COMMANDS[cmd](cmd, enhanced_session, console, agent)
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
            title=Text("Adorable CLI", style="panel_title"),
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


def _is_deletion_command(cmd_text: str) -> bool:
    """Check if a shell command contains deletion operations.
    
    Returns True for commands that delete files or directories:
    - rm, rmdir, unlink, trash
    """
    patterns = [
        r'\brm\b',      # rm command
        r'\brmdir\b',   # rmdir command  
        r'\bunlink\b',  # unlink command
        r'\btrash\b',   # trash command (macOS)
    ]
    import re
    lower = cmd_text.lower()
    return any(re.search(pattern, lower) for pattern in patterns)


def handle_tool_confirmation(tool, console: Console) -> bool:
    """Show tool preview and get user confirmation for deletion commands.
    
    Auto-approves all commands except:
    1. Deletion commands (rm, rmdir, etc.) - shows preview and asks for confirmation
    2. Dangerous commands (rm -rf /, sudo) - hard blocked
    
    Returns True if confirmed or auto-approved, False if denied or blocked.
    """
    tname = getattr(tool, "tool_name", None) or getattr(tool, "name", None) or "tool"
    targs = getattr(tool, "tool_args", None) or {}

    # Hard bans: block dangerous system-level commands regardless
    if tname == "run_shell_command":
        cmd_text = _get_shell_text(targs)
        lower = cmd_text.lower().strip()
        
        # Block critical dangerous patterns
        if "rm -rf /" in lower or " rm -rf / " in lower:
            console.print(Text.from_markup("[error]Blocked dangerous command (hard-ban)[/error]"))
            return False
        if lower.startswith("sudo ") or " sudo " in lower:
            console.print(Text.from_markup("[error]Blocked dangerous command (hard-ban)[/error]"))
            return False
        
        # Auto-approve non-deletion commands
        if not _is_deletion_command(cmd_text):
            return True

    # Show preview and ask confirmation only for deletion commands
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


async def process_agent_stream(
    agent,
    user_input: str,
    renderer: StreamRenderer,
    console: Console,
    *,
    session_id: str | None = None,
    user_id: str | None = None,
) -> tuple[str, Any, datetime, float]:
    """Process agent stream with tool confirmations. Returns (final_text, metrics, start_time, start_perf).

    Async version to support MCPTools and other async tools.
    """
    final_metrics = None
    start_at = datetime.now()
    start_perf = perf_counter()

    stream = agent.arun(
        user_input,
        stream=True,
        stream_intermediate_steps=True,
        session_id=session_id,
        user_id=user_id,
    )
    if inspect.isawaitable(stream):
        stream = await stream

    renderer.start_stream()

    try:
        while True:
            paused_event = None

            if hasattr(stream, "__aiter__"):
                async for event in stream:
                    etype = getattr(event, "event", "")

                    if etype in ("RunContent", "TeamRunContent"):
                        content = getattr(event, "content", "")
                        if content:
                            renderer.update_content(content)

                    if etype in ("RunCompleted", "TeamRunCompleted"):
                        content = getattr(event, "content", "")
                        if content:
                            renderer.set_final_content(content)

                        metrics = getattr(event, "metrics", None)
                        if metrics:
                            final_metrics = metrics

                    if etype in ("ToolCallStarted", "RunToolCallStarted"):
                        renderer.render_tool_call(event)

                    if getattr(event, "is_paused", False):
                        paused_event = event
                        break
            else:
                for event in stream:
                    etype = getattr(event, "event", "")

                    if etype in ("RunContent", "TeamRunContent"):
                        content = getattr(event, "content", "")
                        if content:
                            renderer.update_content(content)

                    if etype in ("RunCompleted", "TeamRunCompleted"):
                        content = getattr(event, "content", "")
                        if content:
                            renderer.set_final_content(content)

                        metrics = getattr(event, "metrics", None)
                        if metrics:
                            final_metrics = metrics

                    if etype in ("ToolCallStarted", "RunToolCallStarted"):
                        renderer.render_tool_call(event)

                    if getattr(event, "is_paused", False):
                        paused_event = event
                        break

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

                stream = agent.acontinue_run(
                    run_id=getattr(paused_event, "run_id", None),
                    updated_tools=getattr(paused_event, "tools", None),
                    stream=True,
                    stream_intermediate_steps=True,
                    session_id=session_id,
                    user_id=user_id,
                )
                if inspect.isawaitable(stream):
                    stream = await stream
                renderer.resume_stream()
            else:
                break
    finally:
        renderer.finish_stream()

    final_text = renderer.get_final_text()
    return final_text, final_metrics, start_at, start_perf


async def run_interactive(agent, *, session_id: str | None = None, user_id: str | None = None) -> int:
    # Get configuration
    try:
        ver = pkg_version("adorable-cli")
    except PackageNotFoundError:
        ver = "version unknown"
    
    model_id = settings.model_id
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
            Align.center(Text("Welcome to Adorable CLI", style="header")),
            Align.center(Text.from_markup(pixel_sprite)),
        )
    else:
        left_group = Group(
            Align.center(Text("Welcome to Adorable CLI", style="header")),
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
        Text(f"Model: {model_id}", style="muted"),
        Text(f"Path: {cwd}", style="muted"),
    )

    console.print(
        Panel(
            Columns([left_group, right_group], equal=True, expand=True),
            title=Text("Adorable CLI", style="panel_title"),
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

    pinned_mcp_tools = await _pin_mcp_tools_to_current_task(agent)

    # Load custom commands
    commands_loader = CommandsLoader(CONFIG_PATH / "commands")
    custom_commands = commands_loader.load_commands()
    if custom_commands:
        console.print(f"[info]Loaded {len(custom_commands)} custom commands[/info]")

    try:
        while True:
            try:
                user_input = await enhanced_session.prompt_user(">> ")
            except KeyboardInterrupt:
                console.print("Bye!", style="info")
                return 0
            except EOFError:
                console.print("Bye!", style="info")
                break

            if not user_input:
                continue

            if handle_special_command(user_input, enhanced_session, console, agent):
                if user_input.strip().lower() in EXIT_COMMANDS:
                    break
                continue

            # Check for custom slash commands
            if user_input.startswith("/"):
                cmd_key = user_input[1:].strip()
                if cmd_key in custom_commands:
                    cmd_obj = custom_commands[cmd_key]
                    console.print(f"[info]Running command /{cmd_key}[/info]")
                    user_input = cmd_obj.prompt

            try:
                final_text, final_metrics, start_at, start_perf = await process_agent_stream(
                    agent,
                    user_input,
                    renderer,
                    console,
                    session_id=session_id,
                    user_id=user_id,
                )
                renderer.render_footer(final_metrics, start_at, start_perf)
            except Exception as exc:
                if _looks_like_mcp_jsonrpc_error(exc):
                    console.print(
                        "[error]MCP tool failed to parse server output (the tool may have exited).[/error]"
                    )
                    console.print(
                        "[muted]Retry the request, or disable MCP with "
                        "ADORABLE_DISABLE_MCP=1 if the issue persists.[/muted]"
                    )
                    continue
                console.print_exception()
    finally:
        await _close_pinned_mcp_tools(pinned_mcp_tools)

    return 0
