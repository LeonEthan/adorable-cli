import os
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from time import perf_counter
from typing import Optional

import typer
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAILike
from agno.session.summary import SessionSummaryManager
from agno.tools.calculator import CalculatorTools
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.file import FileTools
from agno.tools.memory import MemoryTools
from agno.tools.python import PythonTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.shell import ShellTools
from agno.tools.tavily import TavilyTools
from agno.utils.log import configure_agno_logging
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme

from adorable_cli.hooks.context_guard import ensure_context_within_window, restore_context_settings
from adorable_cli.prompt import MAIN_AGENT_DESCRIPTION, MAIN_AGENT_INSTRUCTIONS
from adorable_cli.tools.vision_tool import create_image_understanding_tool
from adorable_cli.ui.enhanced_input import create_enhanced_session
from adorable_cli.ui.stream_renderer import StreamRenderer
from adorable_cli.ui.utils import summarize_args

CONFIG_PATH = Path.home() / ".adorable"
CONFIG_FILE = CONFIG_PATH / "config"
MEM_DB_PATH = CONFIG_PATH / "memory.db"
console = Console()
app = typer.Typer(add_completion=False)
_APP_THEME = Theme(
    {
        "header": "bold orange3",
        "muted": "grey58",
        "tip": "bold dark_orange",
        "panel_border": "blue",
        "rule_light": "grey37",
        "panel_title": "bold white",
        "info": "cyan",
        "success": "green",
        "error": "red",
        "warning": "yellow",
        "tool_line": "cyan",
        "tool_name": "magenta",
        "cat_primary": "sandy_brown",
        "cat_secondary": "navajo_white1",
        "cat_accent": "black",
    }
)


def _configure_console(plain: bool) -> None:
    global console
    if plain:
        console = Console(no_color=True)
    else:
        console = Console(theme=_APP_THEME)


def configure_logging() -> None:
    """Configure Agno logging using built-in helpers and env flags.

    Prefer Agno's native logging configuration over custom wrappers.
    """
    try:
        # Default log levels via environment (respected by Agno)
        os.environ.setdefault("AGNO_LOG_LEVEL", "WARNING")
        os.environ.setdefault("AGNO_TOOLS_LOG_LEVEL", "WARNING")
        # Initialize Agno logging with defaults
        configure_agno_logging()
    except Exception:
        # Non-fatal if logging configuration fails
        pass


def parse_kv_file(path: Path) -> dict[str, str]:
    cfg: dict[str, str] = {}
    if not path.exists():
        return cfg
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            # Strip common quotes/backticks users may include
            cfg[k.strip()] = v.strip().strip('"').strip("'").strip("`")
    return cfg


def write_kv_file(path: Path, data: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in data.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_env_from_config(cfg: dict[str, str]) -> None:
    # Persist requested env vars
    api_key = cfg.get("API_KEY", "")
    base_url = cfg.get("BASE_URL", "")
    tavily_key = cfg.get("TAVILY_API_KEY", "")
    vlm_model_id = cfg.get("VLM_MODEL_ID", "")
    confirm_mode = cfg.get("CONFIRM_MODE", "")
    if api_key:
        os.environ.setdefault("API_KEY", api_key)
        os.environ.setdefault("OPENAI_API_KEY", api_key)
    if base_url:
        os.environ.setdefault("BASE_URL", base_url)
        # Common env var name used by OpenAI clients
        os.environ.setdefault("OPENAI_BASE_URL", base_url)
    if tavily_key:
        os.environ.setdefault("TAVILY_API_KEY", tavily_key)
    model_id = cfg.get("MODEL_ID", "")
    if model_id:
        os.environ.setdefault("ADORABLE_MODEL_ID", model_id)
    if vlm_model_id:
        os.environ.setdefault("ADORABLE_VLM_MODEL_ID", vlm_model_id)
    if confirm_mode:
        os.environ.setdefault("ADORABLE_CONFIRM_MODE", confirm_mode)


def ensure_config_interactive() -> dict[str, str]:
    # Ensure configuration directory exists and read existing config if present
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    cfg: dict[str, str] = {}
    if CONFIG_FILE.exists():
        cfg = parse_kv_file(CONFIG_FILE)

    # Four variables are required: API_KEY, BASE_URL, MODEL_ID, TAVILY_API_KEY
    # One optional variable: VLM_MODEL_ID (for vision language model)
    required_keys = ["API_KEY", "BASE_URL", "MODEL_ID", "TAVILY_API_KEY"]
    missing = [k for k in required_keys if not cfg.get(k, "").strip()]

    if missing:
        setup_message = Text()
        setup_message.append("🔧 Initial or missing configuration\n", style="warning")
        setup_message.append("Required variables:\n", style="bold")
        setup_message.append("• API_KEY\n")
        setup_message.append("• BASE_URL\n")
        setup_message.append("• MODEL_ID\n")
        setup_message.append("• TAVILY_API_KEY\n")
        setup_message.append("\n")
        setup_message.append("💡 Optional: VLM_MODEL_ID for image understanding\n", style="info")
        setup_message.append("(defaults to MODEL_ID if not set)", style="muted")
        setup_message.append("\n")
        setup_message.append("💡 Optional: FAST_MODEL_ID for session summaries\n", style="info")
        setup_message.append("(defaults to MODEL_ID if not set)", style="muted")

        console.print(
            Panel(
                setup_message,
                title=Text("Adorable Setup", style="panel_title"),
                border_style="panel_border",
                padding=(0, 1),
            )
        )

        def prompt_required(label: str) -> str:
            while True:
                v = input(f"Enter {label}: ").strip()
                if v:
                    return sanitize(v)
                console.print(f"{label} cannot be empty.", style="error")

        for key in required_keys:
            if not cfg.get(key, "").strip():
                cfg[key] = prompt_required(key)

        write_kv_file(CONFIG_FILE, cfg)
        console.print(f"✅ Saved to {CONFIG_FILE}", style="success")

    # Load configuration into environment variables
    load_env_from_config(cfg)
    return cfg


def build_agent():
    # Model id can be customized via env MODEL_ID, else defaults
    model_id = os.environ.get("ADORABLE_MODEL_ID", "gpt-5-mini")

    # Read API key and base URL from environment (supports OpenAI-compatible providers)
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("BASE_URL")

    # Summary model id can be customized via FAST_MODEL_ID (or ADORABLE_FAST_MODEL_ID)
    fast_model_id = (
        os.environ.get("FAST_MODEL_ID") or os.environ.get("ADORABLE_FAST_MODEL_ID") or model_id
    )

    # Shared user memory database
    db = SqliteDb(db_file=str(MEM_DB_PATH))

    team_tools = [
        ReasoningTools(add_instructions=True),
        # Calculator tools for numerical calculations and verification
        CalculatorTools(),
        # Web tools
        TavilyTools(),
        Crawl4aiTools(),
        # Standard file operations
        FileTools(base_dir=Path.cwd(), all=True),
        # User memory tools
        MemoryTools(db=db),
        # Default Agno execution tools (Python/Shell)
        PythonTools(base_dir=Path.cwd()),
        ShellTools(base_dir=Path.cwd()),
        # Vision understanding tool
        create_image_understanding_tool(),
    ]

    # Read confirm mode to adjust tool confirmation behavior (only 'normal' and 'auto')
    confirm_mode = os.environ.get("ADORABLE_CONFIRM_MODE", "auto").strip() or "auto"
    if confirm_mode == "off":
        # Backward compatibility: treat deprecated 'off' as 'auto'
        confirm_mode = "auto"

    # Debug configuration from environment
    agno_debug_env = os.environ.get("AGNO_DEBUG", "").strip().lower()
    debug_mode = agno_debug_env in {"1", "true", "yes", "on"}
    debug_level_val = os.environ.get("AGNO_DEBUG_LEVEL", "")
    try:
        debug_level = int(debug_level_val) if debug_level_val else None
    except Exception:
        debug_level = None

    # Configure a dedicated fast model for session summaries if provided
    # Configure SessionSummaryManager to avoid JSON/structured outputs to prevent parsing warnings
    session_summary_manager = SessionSummaryManager(
        model=OpenAILike(
            id=fast_model_id,
            api_key=api_key,
            base_url=base_url,
            # Smaller cap is sufficient for summaries; providers may ignore
            max_tokens=4096,
            # Force plain-text outputs for summaries to avoid JSON parsing attempts
            supports_native_structured_outputs=False,
            supports_json_schema_outputs=False,
        ),
        # Ask for a plain-text summary only; no JSON or lists
        session_summary_prompt=(
            "Provide a concise plain-text summary of the recent conversation. "
            "Do not return JSON, XML, lists, or keys. Return one short paragraph."
        ),
    )

    main_agent = Agent(
        name="adorable",
        model=OpenAILike(
            id=model_id,
            api_key=api_key,
            base_url=base_url,
            max_tokens=8192,
        ),
        # system prompt (session-state)
        description=MAIN_AGENT_DESCRIPTION,
        instructions=MAIN_AGENT_INSTRUCTIONS,
        add_datetime_to_context=True,
        # todo list management using session state
        session_state={
            "todos": [],
        },
        enable_agentic_state=True,
        add_session_state_to_context=True,
        # TODO: subagents/workflow
        # tools
        tools=team_tools,
        # memory
        db=db,
        # Long-term memory
        enable_session_summaries=True,
        session_summary_manager=session_summary_manager,
        add_session_summary_to_context=True,
        # Short-term memory
        add_history_to_context=True,
        num_history_runs=3,
        max_tool_calls_from_history=3,
        # output format
        markdown=True,
        # built-in debug toggles
        debug_mode=debug_mode,
        **({"debug_level": debug_level} if debug_level is not None else {}),
        # Retry strategy
        exponential_backoff=True,
        retries=2,
        delay_between_retries=1,
        # Context guard hooks
        pre_hooks=[ensure_context_within_window],
        post_hooks=[restore_context_settings],
    )

    # Confirmation behavior per mode
    if confirm_mode in ("normal", "auto"):
        try:
            for toolkit in team_tools:
                functions = getattr(toolkit, "functions", {})
                # First clear all
                for f in functions.values():
                    try:
                        setattr(f, "requires_confirmation", False)
                    except Exception:
                        pass
                # Enable per-mode targets
                for name, f in functions.items():
                    # Python: support both Agno default and legacy wrapper names
                    python_names = {"execute_python_code", "run_python_code"}
                    shell_names = {"run_shell_command"}
                    file_save = {"save_file"}
                    try:
                        if confirm_mode in ("normal", "auto") and (
                            name in python_names or name in shell_names
                        ):
                            setattr(f, "requires_confirmation", True)
                        if confirm_mode == "normal" and name in file_save:
                            setattr(f, "requires_confirmation", True)
                    except Exception:
                        pass
        except Exception:
            pass

    return main_agent


def print_version() -> int:
    try:
        ver = pkg_version("adorable-cli")
        print(f"adorable-cli {ver}")
    except PackageNotFoundError:
        # Fallback when distribution metadata is unavailable (e.g., dev runs)
        print("adorable-cli (version unknown)")
    return 0


def sanitize(val: str) -> str:
    return val.strip().strip('"').strip("'").strip("`")


def detect_language_from_extension(file_path: str) -> str:
    try:
        ext = Path(file_path).suffix.lower()
    except Exception:
        ext = ""
    mapping = {
        ".py": "python",
        ".sh": "bash",
        ".bash": "bash",
        ".js": "javascript",
        ".ts": "typescript",
        ".json": "json",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".html": "html",
        ".css": "css",
    }
    return mapping.get(ext, "")


def run_config() -> int:
    console.print(
        Panel(
            "Configure API_KEY, BASE_URL, MODEL_ID, TAVILY_API_KEY, VLM_MODEL_ID, FAST_MODEL_ID",
            title=Text("Adorable Config", style="panel_title"),
            border_style="panel_border",
            padding=(0, 1),
        )
    )
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    existing = parse_kv_file(CONFIG_FILE)
    current_key = existing.get("API_KEY", "")
    current_url = existing.get("BASE_URL", "")
    current_model = existing.get("MODEL_ID", "")
    current_tavily = existing.get("TAVILY_API_KEY", "")
    current_vlm_model = existing.get("VLM_MODEL_ID", "")
    current_fast_model = existing.get("FAST_MODEL_ID", "")

    console.print(Text(f"Current API_KEY: {current_key or '(empty)'}", style="info"))
    api_key = input("Enter new API_KEY (leave blank to keep): ")
    console.print(Text(f"Current BASE_URL: {current_url or '(empty)'}", style="info"))
    base_url = input("Enter new BASE_URL (leave blank to keep): ")
    console.print(Text(f"Current MODEL_ID: {current_model or '(empty)'}", style="info"))
    model_id = input("Enter new MODEL_ID (leave blank to keep): ")
    console.print(Text(f"Current TAVILY_API_KEY: {current_tavily or '(empty)'}", style="info"))
    tavily_api_key = input("Enter new TAVILY_API_KEY (leave blank to keep): ")
    console.print(Text(f"Current VLM_MODEL_ID: {current_vlm_model or '(empty)'}", style="info"))
    console.print(
        Text(
            "VLM_MODEL_ID is used for image understanding (optional, defaults to MODEL_ID)",
            style="muted",
        )
    )
    vlm_model_id = input("Enter new VLM_MODEL_ID (leave blank to keep): ")

    console.print(Text(f"Current FAST_MODEL_ID: {current_fast_model or '(empty)'}", style="info"))
    console.print(
        Text(
            "FAST_MODEL_ID is used for session summaries (optional, defaults to MODEL_ID)",
            style="muted",
        )
    )
    fast_model_id = input("Enter new FAST_MODEL_ID (leave blank to keep): ")

    new_cfg = dict(existing)
    if api_key.strip():
        new_cfg["API_KEY"] = sanitize(api_key)
    if base_url.strip():
        new_cfg["BASE_URL"] = sanitize(base_url)
    if model_id.strip():
        new_cfg["MODEL_ID"] = sanitize(model_id)
    if tavily_api_key.strip():
        new_cfg["TAVILY_API_KEY"] = sanitize(tavily_api_key)
    if vlm_model_id.strip():
        new_cfg["VLM_MODEL_ID"] = sanitize(vlm_model_id)
    if fast_model_id.strip():
        new_cfg["FAST_MODEL_ID"] = sanitize(fast_model_id)

    write_kv_file(CONFIG_FILE, new_cfg)
    load_env_from_config(new_cfg)
    console.print(f"✅ Saved to {CONFIG_FILE}", style="success")
    return 0


def run_interactive(agent) -> int:
    # Claude Code-style welcome UI: two-column layout + simple pixel icon
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

    # Left panel: show larger pixel cat image (preserve more lines)
    try:
        ver = pkg_version("adorable-cli")
    except PackageNotFoundError:
        ver = "version unknown"
    model_id = os.environ.get("ADORABLE_MODEL_ID", "gpt-5-mini")
    cwd = str(Path.cwd())

    left_group = Group(
        Align.center(Text("Welcome use Adorable CLI!", style="header")),
        Align.center(Text.from_markup(pixel_sprite)),
    )

    # Right panel: getting started tips + recent activity (preserve layout)
    # Confirm mode from env (default: auto)
    confirm_mode = os.environ.get("ADORABLE_CONFIRM_MODE", "auto").strip() or "auto"

    right_group = Group(
        Text("Tips for getting started", style="tip"),
        Rule(style="rule_light"),
        Text("• Run `uv run ador` to enter interactive mode", style="muted"),
        Text("• Run `uv run adorable config` to configure API and model", style="muted"),
        Text("• Enhanced input: History completion, multiline editing", style="muted"),
        Text("• Type 'help-input' for enhanced input features", style="muted"),
        Text("Config", style="tip"),
        Rule(style="rule_light"),
        Text(f"Adorable CLI {ver} • Model {model_id}", style="muted"),
        Text(f"Confirm Mode: {confirm_mode}", style="muted"),
        Text(f"{cwd}", style="muted"),
    )

    console.print(
        Panel(
            Columns([left_group, right_group], equal=True, expand=True),
            title=Text("Adorable", style="panel_title"),
            border_style="panel_border",
            padding=(0, 1),
        )
    )

    # Create enhanced input session
    enhanced_session = create_enhanced_session(console)

    # Enhanced interaction loop with prompt-toolkit
    exit_on = ["exit", "exit()", "quit", "q", "bye"]
    special_commands = ["help-input", "clear", "cls", "session-stats", "enhanced-mode"]

    console.print("[success]✨ Enhanced CLI enabled![/success]")
    console.print(
        "[tip]🎯 Features: History completion • Multiline editing • Command history[/tip]"
    )
    console.print(
        "[muted]Input: Enter=submit, Ctrl+J=newline • Type 'help-input' for shortcuts[/muted]"
    )

    # Stream rendering handled in loop with unified StreamRenderer

    while True:
        try:
            # Use enhanced input session
            user_input = enhanced_session.prompt_user("> ")
        except KeyboardInterrupt:
            console.print("👋 Bye!", style="warning")
            return 0
        except EOFError:
            break

        if not user_input:
            continue

        # Handle special commands
        if user_input.lower() in exit_on:
            console.print("👋 Bye!", style="warning")
            break
        # Session-level confirm mode commands: /auto, /normal
        if user_input.strip().lower() in {"/auto", "/normal"}:
            new_mode = user_input.strip().lower()[1:]
            os.environ["ADORABLE_CONFIRM_MODE"] = new_mode
            apply_confirm_mode_to_agent(agent, new_mode)
            # Update local session confirm_mode for subsequent auto_confirm logic
            confirm_mode = new_mode
            console.print(f"✅ Switched confirm mode to: {new_mode}", style="success")
            # Show lightweight status panel
            status = Group(
                Text(f"Confirm Mode: {new_mode}", style="muted"),
                Text("Subsequent tool calls will follow the new mode", style="muted"),
            )
            console.print(
                Panel(
                    status,
                    title=Text("Session Update", style="panel_title"),
                    border_style="panel_border",
                    padding=(0, 1),
                )
            )
            continue
        elif user_input.lower() in special_commands:
            if user_input.lower() == "help-input":
                enhanced_session.show_quick_help()
                continue
            elif user_input.lower() in ["clear", "cls"]:
                console.clear()
                continue
            elif user_input.lower() == "session-stats":
                console.print(
                    Panel(
                        Text(
                            "📊 Current Session Stats:\n"
                            "• Enhanced Input: Enabled\n"
                            "• History Completion: Enabled\n"
                            "• Multiline Editing: Enabled",
                            style="muted",
                        ),
                        title=Text("Session Stats", style="panel_title"),
                        border_style="panel_border",
                        padding=(0, 1),
                    )
                )
                continue
            elif user_input.lower() == "enhanced-mode":
                console.print(
                    Panel(
                        Text(
                            "🚀 Enhanced Mode Features:\n\n"
                            "• [info]History Input[/info]: Command history and auto-completion\n"
                            "• [success]Multiline Editing[/success]: Support Ctrl+J for newline input\n"
                            "• [warning]Smart Suggestions[/warning]: Command and parameter auto-completion",
                        ),
                        title=Text("Enhanced Mode", style="panel_title"),
                        border_style="panel_border",
                        padding=(0, 1),
                    )
                )
                continue

        try:
            # Streamed rendering with HITL confirmations
            final_text = ""
            final_metrics = None
            start_at = datetime.now()
            start_perf = perf_counter()
            stream = agent.run(user_input, stream=True, stream_intermediate_steps=True)

            # Helper: summarize args like StreamRenderer
            # Use shared summarize_args from ui.utils for argument previews

            # Risk classifiers
            def get_shell_text(targs: dict) -> str:
                """Normalize shell tool args to a single command text for checks/preview."""
                val = targs.get("command", None)
                if val is None:
                    val = targs.get("args", None) or targs.get("argv", None)
                if isinstance(val, (list, tuple)):
                    return " ".join(str(x) for x in val)
                return str(val or "")

            # No custom risk classification; rely on Agno's built-in pause + confirmation

            # Initialize unified renderer for ToolCall lines
            renderer = StreamRenderer(console)

            # Process stream with pause handling
            while True:
                paused_event = None
                for event in stream:
                    etype = getattr(event, "event", "")

                    if etype in ("RunCompleted",):
                        final_text = getattr(event, "content", "")
                        final_metrics = getattr(event, "metrics", None)

                    if etype in ("ToolCallStarted", "RunToolCallStarted"):
                        # Delegate ToolCall line rendering to unified renderer
                        renderer.handle_event(event)

                    if getattr(event, "is_paused", False):
                        paused_event = event
                        break

                if paused_event is not None:
                    # Confirm tools requiring approval
                    tools_list = (
                        getattr(paused_event, "tools_requiring_confirmation", None)
                        or getattr(paused_event, "tools", None)
                        or []
                    )

                    for tool in tools_list:
                        tname = (
                            getattr(tool, "tool_name", None)
                            or getattr(tool, "name", None)
                            or "tool"
                        )
                        targs = getattr(tool, "tool_args", None) or {}
                        # No per-argument risk classification

                        # Hard bans: block dangerous system-level commands regardless of mode
                        hard_ban = False
                        if tname == "run_shell_command":
                            cmd_text = get_shell_text(targs)
                            lower = cmd_text.lower().strip()
                            if "rm -rf /" in lower:
                                hard_ban = True
                            if lower.startswith("sudo ") or " sudo " in lower:
                                hard_ban = True
                        if hard_ban:
                            setattr(tool, "confirmed", False)
                            console.print(
                                Text.from_markup(
                                    "[error]Blocked dangerous command (hard-ban)[/error]"
                                )
                            )
                            continue

                        # Auto mode: still pause Python/Shell for hard-ban checks, then auto-confirm
                        auto_confirm = confirm_mode == "auto"
                        if auto_confirm:
                            setattr(tool, "confirmed", True)
                        else:
                            # Show detailed content preview for confirmation
                            preview_group = []
                            header_text = Text(f"Tool: {tname}", style="tool_name")
                            preview_group.append(header_text)
                            try:
                                if tname == "execute_python_code":
                                    code = str(targs.get("code", ""))
                                    code_display = (
                                        code if len(code) <= 2000 else (code[:1970] + "...")
                                    )
                                    preview_group.append(
                                        Syntax(
                                            code_display,
                                            "python",
                                            theme="monokai",
                                            line_numbers=False,
                                        )
                                    )
                                elif tname == "run_shell_command":
                                    cmd = get_shell_text(targs)
                                    cmd_display = cmd if len(cmd) <= 1000 else (cmd[:970] + "...")
                                    preview_group.append(
                                        Syntax(
                                            cmd_display, "bash", theme="monokai", line_numbers=False
                                        )
                                    )
                                elif tname == "save_file":
                                    # Support multiple arg names used by FileTools
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
                                    content_display = (
                                        content
                                        if len(content) <= 2000
                                        else (content[:1970] + "...")
                                    )
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
                                    summary = summarize_args(
                                        targs if isinstance(targs, dict) else {}
                                    )
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
                            setattr(tool, "confirmed", resp == "y")

                    stream = agent.continue_run(
                        run_id=getattr(paused_event, "run_id", None),
                        updated_tools=getattr(paused_event, "tools", None),
                        stream=True,
                        stream_intermediate_steps=True,
                    )
                    continue
                else:
                    break

            # Final result display
            # Use Text with style instead of passing style to from_markup (unsupported)
            console.print(Text("🐱 Adorable:", style="header"))
            console.print(Markdown(final_text or ""))

            renderer.render_footer(final_metrics, start_at, start_perf)
        except Exception:
            console.print_exception()

    return 0


@app.callback(invoke_without_command=True)
def app_entry(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(None, "--model"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    fast_model: Optional[str] = typer.Option(None, "--fast-model"),
    confirm_mode_opt: Optional[str] = typer.Option(None, "--confirm-mode"),
    debug: bool = typer.Option(False, "--debug"),
    debug_level: Optional[int] = typer.Option(None, "--debug-level"),
    plain: bool = typer.Option(False, "--plain"),
) -> None:
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ.setdefault("API_KEY", api_key)
    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url
        os.environ.setdefault("BASE_URL", base_url)
    if model:
        os.environ["ADORABLE_MODEL_ID"] = model
    if fast_model:
        os.environ["ADORABLE_FAST_MODEL_ID"] = fast_model
    if confirm_mode_opt and confirm_mode_opt.lower() in {"normal", "auto"}:
        os.environ["ADORABLE_CONFIRM_MODE"] = confirm_mode_opt.lower()
    if debug:
        os.environ["AGNO_DEBUG"] = "1"
    if debug_level is not None:
        os.environ["AGNO_DEBUG_LEVEL"] = str(debug_level)
    _configure_console(plain)
    if ctx.invoked_subcommand is None:
        cfg = ensure_config_interactive()
        cm = cfg.get("CONFIRM_MODE", "").strip()
        if cm:
            os.environ.setdefault("ADORABLE_CONFIRM_MODE", cm)
        configure_logging()
        agent = build_agent()
        code = run_interactive(agent)
        raise typer.Exit(code)


@app.command()
def version() -> None:
    code = print_version()
    raise typer.Exit(code)


@app.command()
def config() -> None:
    code = run_config()
    raise typer.Exit(code)


@app.command()
def mode(set: Optional[str] = typer.Option(None, "--set", "-s")) -> None:
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    existing = parse_kv_file(CONFIG_FILE)
    current_mode = (
        existing.get("CONFIRM_MODE", os.environ.get("ADORABLE_CONFIRM_MODE", "auto")) or "auto"
    )
    if set and set.lower() in {"normal", "auto"}:
        new_mode = set.lower()
        existing["CONFIRM_MODE"] = new_mode
        write_kv_file(CONFIG_FILE, existing)
        os.environ["ADORABLE_CONFIRM_MODE"] = new_mode
        console.print(f"✅ Confirm mode set to: {new_mode}")
        raise typer.Exit(0)
    console.print(f"Current confirm mode: {current_mode}")
    console.print(Text("Use: adorable mode --set [normal|auto]"))
    raise typer.Exit(0)


@app.command()
def chat() -> None:
    cfg = ensure_config_interactive()
    cm = cfg.get("CONFIRM_MODE", "").strip()
    if cm:
        os.environ.setdefault("ADORABLE_CONFIRM_MODE", cm)
    configure_logging()
    agent = build_agent()
    code = run_interactive(agent)
    raise typer.Exit(code)


def main() -> int:
    app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def apply_confirm_mode_to_agent(agent, mode: str) -> None:
    """Dynamically adjust requires_confirmation flags on the existing agent's tools.

    - normal: confirm python, shell, and save_file; others off
    - auto: confirm python and shell only; others off (auto-continue after hard-ban checks)
    """
    try:
        target_true = set()
        python_names = {"execute_python_code", "run_python_code"}
        shell_names = {"run_shell_command"}
        file_names = {"save_file"}

        if mode == "normal":
            target_true = set().union(python_names, shell_names, file_names)
        elif mode == "auto":
            target_true = set().union(python_names, shell_names)
        # Deprecated 'off' mode is treated as 'auto' elsewhere; no special handling here.

        for tk in getattr(agent, "tools", []):
            functions = getattr(tk, "functions", {})
            # First set all to False
            for f in functions.values():
                try:
                    setattr(f, "requires_confirmation", False)
                except Exception:
                    pass
            # Then enable target ones
            for name, f in functions.items():
                if name in target_true:
                    try:
                        setattr(f, "requires_confirmation", True)
                    except Exception:
                        pass
    except Exception:
        # Non-fatal
        pass
