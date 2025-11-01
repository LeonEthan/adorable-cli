import logging
import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAILike
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
from rich.text import Text

from adorable_cli.prompt import MAIN_AGENT_DESCRIPTION, MAIN_AGENT_INSTRUCTIONS
from adorable_cli.tools.vision_tool import create_image_understanding_tool
from adorable_cli.ui.enhanced_input import create_enhanced_session
from adorable_cli.ui.enhanced_renderer_simple import create_simple_enhanced_renderer
from adorable_cli.ui.stream_renderer import StreamRenderer
from adorable_cli.ui.utils import summarize_args

CONFIG_PATH = Path.home() / ".adorable"
CONFIG_FILE = CONFIG_PATH / "config"
MEM_DB_PATH = CONFIG_PATH / "memory.db"
console = Console()


def configure_logging() -> None:
    """Reduce Agno logs to WARNING to avoid initial INFO noise.

    On first run, Agno's SqliteDb creates tables and logs at INFO level.
    Lowering the logger level prevents this message from interrupting
    the first user interaction in the CLI.
    """
    try:
        # Global default logger level (fallback)
        logging.getLogger().setLevel(logging.WARNING)
        # Core Agno loggers
        logging.getLogger("agno").setLevel(logging.WARNING)
        logging.getLogger("agno.agent").setLevel(logging.WARNING)
        logging.getLogger("agno.db").setLevel(logging.WARNING)
        logging.getLogger("agno.db.sqlite").setLevel(logging.WARNING)
        # Tooling loggers (suppress INFO like "Running shell command" / "Reading files")
        logging.getLogger("agno.tools").setLevel(logging.WARNING)
        logging.getLogger("agno.tools.shell").setLevel(logging.WARNING)
        logging.getLogger("agno.tools.file").setLevel(logging.WARNING)
        logging.getLogger("agno.tools.python").setLevel(logging.WARNING)
        logging.getLogger("agno.utils.log").setLevel(logging.WARNING)

        # Provide a custom default logger to Agno to silence INFO from toolkits
        silent_logger = logging.getLogger("adorable_cli_silent")
        if not silent_logger.handlers:
            # Use a NullHandler so no logs are emitted by default
            silent_logger.addHandler(logging.NullHandler())
        silent_logger.setLevel(logging.WARNING)
        silent_logger.propagate = False
        configure_agno_logging(custom_default_logger=silent_logger)

        # Environment-based fallback for upstream log level controls (if respected)
        os.environ.setdefault("AGNO_LOG_LEVEL", "WARNING")
        os.environ.setdefault("AGNO_TOOLS_LOG_LEVEL", "WARNING")
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
        setup_message.append("🔧 Initial or missing configuration\n", style="bold yellow")
        setup_message.append("Required variables:\n", style="bold")
        setup_message.append("• API_KEY\n")
        setup_message.append("• BASE_URL\n")
        setup_message.append("• MODEL_ID\n")
        setup_message.append("• TAVILY_API_KEY\n")
        setup_message.append("\n")
        setup_message.append(
            "💡 Optional: VLM_MODEL_ID for image understanding\n", style="bold cyan"
        )
        setup_message.append("(defaults to MODEL_ID if not set)", style="dim")

        console.print(
            Panel(
                setup_message,
                title="Adorable Setup",
                border_style="yellow",
                padding=(0, 1),
            )
        )

        def prompt_required(label: str) -> str:
            while True:
                v = input(f"Enter {label}: ").strip()
                if v:
                    return sanitize(v)
                console.print(f"{label} cannot be empty.", style="red")

        for key in required_keys:
            if not cfg.get(key, "").strip():
                cfg[key] = prompt_required(key)

        write_kv_file(CONFIG_FILE, cfg)
        console.print(f"✅ Saved to {CONFIG_FILE}", style="green")

    # Load configuration into environment variables
    load_env_from_config(cfg)
    return cfg


def build_agent():
    # Model id can be customized via env MODEL_ID, else defaults
    model_id = os.environ.get("ADORABLE_MODEL_ID", "gpt-5-mini")

    # Read API key and base URL from environment (supports OpenAI-compatible providers)
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("BASE_URL")

    # Shared user memory database
    db = SqliteDb(db_file=str(MEM_DB_PATH))

    team_tools = [
        ReasoningTools(),
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

    # Read confirm mode to adjust tool confirmation behavior
    confirm_mode = os.environ.get("ADORABLE_CONFIRM_MODE", "auto").strip() or "auto"

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
        # Make the agent aware of the session history
        add_history_to_context=True,
        num_history_runs=3,
        # output format
        markdown=True,
    )

    # Confirmation behavior per mode
    if confirm_mode in ("normal", "auto", "off"):
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
                        # Off mode: still pause Python/Shell to allow hard-ban enforcement, then auto-confirm
                        if confirm_mode == "off" and (name in python_names or name in shell_names):
                            setattr(f, "requires_confirmation", True)
                        if confirm_mode == "normal" and name in file_save:
                            setattr(f, "requires_confirmation", True)
                    except Exception:
                        pass
        except Exception:
            pass

    return main_agent


def print_help():
    help_text = Text()
    help_text.append("Adorable CLI - Agno-based command-line assistant\n", style="bold cyan")
    help_text.append("Usage:\n", style="bold")
    help_text.append("  adorable               Enter interactive chat mode\n")
    help_text.append(
        "  adorable config        Configure API_KEY, BASE_URL, TAVILY_API_KEY, MODEL_ID and VLM_MODEL_ID\n"
    )
    help_text.append("  adorable mode [normal|auto|off]   Set or view confirm mode\n")
    help_text.append("  adorable --help        Show help information\n")
    help_text.append("Examples:\n", style="bold")
    help_text.append("  adorable\n")
    help_text.append("  adorable config\n")
    help_text.append("Notes:\n", style="bold")
    help_text.append(
        "  - On first run, you must set four required variables: API_KEY, BASE_URL, MODEL_ID, TAVILY_API_KEY; configuration is stored at ~/.adorable/config\n"
    )
    help_text.append("  - MODEL_ID can be set via `adorable config` (e.g., glm-4-flash)\n")
    help_text.append(
        "  - VLM_MODEL_ID is optional and used for image understanding; defaults to MODEL_ID if not set\n"
    )
    help_text.append(
        "  - TAVILY_API_KEY is set via `adorable config` to enable web search (Tavily)\n"
    )
    help_text.append(
        "  - Security: built-in safety policy enforced by the confirmation layer; no external security.yaml\n"
    )
    help_text.append(
        "  - Confirm Mode: 'normal' asks before all tool runs; 'auto' asks only for risky ops; 'off' auto-confirms\n"
    )
    help_text.append("  - Press Enter to submit; Ctrl+C/Ctrl+D to exit\n")
    console.print(Panel(help_text, title="Help", border_style="blue", padding=(0, 1)))


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


def run_config() -> int:
    console.print(
        Panel(
            "Configure API_KEY, BASE_URL, MODEL_ID, TAVILY_API_KEY, VLM_MODEL_ID",
            title="Adorable Config",
            border_style="yellow",
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

    console.print(Text(f"Current API_KEY: {current_key or '(empty)'}", style="cyan"))
    api_key = input("Enter new API_KEY (leave blank to keep): ")
    console.print(Text(f"Current BASE_URL: {current_url or '(empty)'}", style="cyan"))
    base_url = input("Enter new BASE_URL (leave blank to keep): ")
    console.print(Text(f"Current MODEL_ID: {current_model or '(empty)'}", style="cyan"))
    model_id = input("Enter new MODEL_ID (leave blank to keep): ")
    console.print(Text(f"Current TAVILY_API_KEY: {current_tavily or '(empty)'}", style="cyan"))
    tavily_api_key = input("Enter new TAVILY_API_KEY (leave blank to keep): ")
    console.print(Text(f"Current VLM_MODEL_ID: {current_vlm_model or '(empty)'}", style="cyan"))
    console.print(
        Text(
            "VLM_MODEL_ID is used for image understanding (optional, defaults to MODEL_ID)",
            style="dim",
        )
    )
    vlm_model_id = input("Enter new VLM_MODEL_ID (leave blank to keep): ")

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

    write_kv_file(CONFIG_FILE, new_cfg)
    load_env_from_config(new_cfg)
    console.print(f"✅ Saved to {CONFIG_FILE}", style="green")
    return 0


def run_interactive(agent) -> int:
    # Claude Code-style welcome UI: two-column layout + simple pixel icon
    pixel_sprite = r"""
[sandy_brown]      ████          ████      [/sandy_brown]
[sandy_brown]      ██[/sandy_brown][navajo_white1]██[/navajo_white1][sandy_brown]██      ██[/sandy_brown][navajo_white1]██[/navajo_white1][sandy_brown]██[/sandy_brown]
[sandy_brown]      ██[/sandy_brown][navajo_white1]████[/navajo_white1][sandy_brown]██████[/sandy_brown][navajo_white1]████[/navajo_white1][sandy_brown]██[/sandy_brown]
[sandy_brown]    ██[/sandy_brown][navajo_white1]██████████████████[/navajo_white1][sandy_brown]██[/sandy_brown]
[sandy_brown]    ██[/sandy_brown][navajo_white1]████[/navajo_white1][black]██[/black][navajo_white1]██████[/navajo_white1][black]██[/black][navajo_white1]████[/navajo_white1][sandy_brown]██[/sandy_brown]
[sandy_brown]    ██[/sandy_brown][navajo_white1]██████████████████[/navajo_white1][sandy_brown]██[/sandy_brown]
[sandy_brown]    ████[/sandy_brown][navajo_white1]██████████████[/navajo_white1][sandy_brown]████[/sandy_brown]
[sandy_brown]        ██████████████[/sandy_brown]
"""

    # Left panel: show larger pixel cat image (preserve more lines)
    try:
        ver = pkg_version("adorable-cli")
    except PackageNotFoundError:
        ver = "version unknown"
    model_id = os.environ.get("ADORABLE_MODEL_ID", "gpt-5-mini")
    cwd = str(Path.cwd())
    cfg_path = str(CONFIG_FILE)

    left_group = Group(
        Align.center(Text("Welcome use Adorable CLI!", style="bold white")),
        Align.center(Text.from_markup(pixel_sprite)),
    )

    # Right panel: getting started tips + recent activity (preserve layout)
    # Confirm mode from env (default: auto)
    confirm_mode = os.environ.get("ADORABLE_CONFIRM_MODE", "auto").strip() or "auto"

    right_group = Group(
        Text("Tips for getting started", style="bold dark_orange"),
        Rule(style="grey37"),
        Text("• Run `uv run ador` to enter interactive mode"),
        Text("• Run `uv run adorable config` to configure API and model"),
        Text("• Enhanced input: History completion, multiline editing"),
        Text("• Type 'help-input' for enhanced input features"),
        Text("Config", style="bold dark_orange"),
        Rule(style="grey37"),
        Text(f"Adorable CLI {ver} • Model {model_id}", style="grey58"),
        Text(f"Confirm Mode: {confirm_mode}", style="grey58"),
        Text(f"{cwd}", style="grey58"),
    )

    console.print(
        Panel(
            Columns([left_group, right_group], equal=True, expand=True),
            title="Adorable",
            border_style="dark_orange",
            padding=(0, 1),
        )
    )

    # Create enhanced input session
    enhanced_session = create_enhanced_session(console)

    # Enhanced interaction loop with prompt-toolkit
    exit_on = ["exit", "exit()", "quit", "q", "bye"]
    special_commands = ["help-input", "clear", "cls", "session-stats", "enhanced-mode"]

    console.print("[green]✨ Enhanced CLI enabled![/green]")
    console.print(
        "[cyan]🎯 Features: History completion • Multiline editing • Command history[/cyan]"
    )
    console.print(
        "[dim]Input: Enter=submit, Ctrl+J=newline • Type 'help-input' for shortcuts[/dim]"
    )

    # Create enhanced renderer (stream printing handled in loop for HITL)
    _ = create_simple_enhanced_renderer(
        console, enable_diff_display=False, enable_confirmations=False
    )

    while True:
        try:
            # Use enhanced input session
            user_input = enhanced_session.prompt_user("> ")
        except KeyboardInterrupt:
            console.print("👋 Bye!", style="yellow")
            return 0
        except EOFError:
            break

        if not user_input:
            continue

        # Handle special commands
        if user_input.lower() in exit_on:
            console.print("👋 Bye!", style="yellow")
            break
        # Session-level confirm mode commands: /auto, /normal, /off
        if user_input.strip().lower() in {"/auto", "/normal", "/off"}:
            new_mode = user_input.strip().lower()[1:]
            os.environ["ADORABLE_CONFIRM_MODE"] = new_mode
            apply_confirm_mode_to_agent(agent, new_mode)
            # Update local session confirm_mode for subsequent auto_confirm logic
            confirm_mode = new_mode
            console.print(f"✅ Switched confirm mode to: {new_mode}", style="green")
            # Show lightweight status panel
            status = Group(
                Text(f"Confirm Mode: {new_mode}", style="grey58"),
                Text("Subsequent tool calls will follow the new mode", style="grey58"),
            )
            console.print(
                Panel(status, title="Session Update", border_style="blue", padding=(0, 1))
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
                            "• Multiline Editing: Enabled"
                        ),
                        title="Session Stats",
                        border_style="blue",
                        padding=(0, 1),
                    )
                )
                continue
            elif user_input.lower() == "enhanced-mode":
                console.print(
                    Panel(
                        Text(
                            "🚀 Enhanced Mode Features:\n\n"
                            "• [cyan]History Input[/cyan]: Command history and auto-completion\n"
                            "• [green]Multiline Editing[/green]: Support Ctrl+J for newline input\n"
                            "• [yellow]Smart Suggestions[/yellow]: Command and parameter auto-completion"
                        ),
                        title="Enhanced Mode",
                        border_style="green",
                        padding=(0, 1),
                    )
                )
                continue

        try:
            # Streamed rendering with HITL confirmations
            final_text = ""
            final_metrics = None
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

            def classify_python_risk(code: str) -> str:
                # Relaxed detection: flag as dangerous only on clearly destructive operations
                text = (code or "").lower()
                destructive_markers = [
                    "os.remove(",
                    "os.unlink(",
                    "shutil.rmtree(",
                    "os.rmdir(",
                    ".unlink(",  # Path(...).unlink()
                    ".rmdir(",  # Path(...).rmdir()
                    "rm -rf",
                    " rm ",
                ]
                risky = any(marker in text for marker in destructive_markers)
                return "danger" if risky else "safe"

            def classify_shell_risk(command_or_args: object) -> str:
                """Classify shell risk, robust to list/tuple or string inputs.

                - Treat any `rm` invocation as dangerous (including `rm -rf`)
                - Otherwise safe
                """
                if isinstance(command_or_args, (list, tuple)):
                    cmd_text = " ".join(str(x) for x in command_or_args)
                else:
                    cmd_text = str(command_or_args or "")
                lower = cmd_text.strip().lower()
                tokens = lower.split()
                base = tokens[0] if tokens else ""
                destructive_bases = {"rm"}
                risky = (base in destructive_bases) or ("rm -rf" in lower)
                return "danger" if risky else "safe"

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
                        risk = "safe"
                        if tname in ("execute_python_code", "run_python_code"):
                            risk = classify_python_risk(str(targs.get("code", "")))
                        elif tname == "run_shell_command":
                            # Support either string command or args list
                            cmd_input = targs.get("command", None)
                            if cmd_input is None:
                                cmd_input = targs.get("args", None) or targs.get("argv", None)
                            risk = classify_shell_risk(cmd_input)

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
                                Text.from_markup("[red]Blocked dangerous command (hard-ban)[/red]")
                            )
                            continue

                        auto_confirm = (confirm_mode == "off") or (
                            confirm_mode == "auto" and risk == "safe"
                        )
                        if auto_confirm:
                            setattr(tool, "confirmed", True)
                        else:
                            # Show detailed content preview for confirmation
                            preview_group = []
                            header_text = Text(
                                f"Tool: {tname} • Risk: {risk}", style="bold magenta"
                            )
                            preview_group.append(header_text)
                            try:
                                if tname == "execute_python_code":
                                    code = str(targs.get("code", ""))
                                    # Limit huge code blocks for readability
                                    code_display = (
                                        code if len(code) <= 2000 else (code[:1970] + "...")
                                    )
                                    preview_group.append(
                                        Text.from_markup(f"```python\n{code_display}\n```")
                                    )
                                elif tname == "run_shell_command":
                                    cmd = get_shell_text(targs)
                                    cmd_display = cmd if len(cmd) <= 1000 else (cmd[:970] + "...")
                                    preview_group.append(Text(f"```bash\n{cmd_display}\n```"))
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
                                        Text(f"Save path: {file_path}", style="cyan")
                                        if file_path
                                        else Text("Save path not provided", style="red")
                                    )
                                    preview_group.append(info)
                                    if content_display:
                                        preview_group.append(
                                            Text.from_markup(f"```\n{content_display}\n```")
                                        )
                                else:
                                    # Generic args preview
                                    summary = summarize_args(
                                        targs if isinstance(targs, dict) else {}
                                    )
                                    preview_group.append(Text(f"Args: {summary}", style="cyan"))
                            except Exception:
                                pass

                            console.print(
                                Panel(
                                    Group(*preview_group),
                                    title="Tool Call Preview",
                                    border_style="cyan",
                                    padding=(0, 1),
                                )
                            )

                            resp = Prompt.ask(
                                f"Confirm running tool [magenta]{tname}[/magenta] (risk={risk})?",
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
            console.print(Text("🐱 Adorable:", style="bold orange3"))
            console.print(Markdown(final_text or ""))

            # Session footer: time and tokens (no start time here; keep metrics if available)
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
                console.print(tokens_line)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")

    return 0


def main() -> int:
    # Version handling
    if any(arg in ("-V", "--version") for arg in sys.argv[1:]):
        return print_version()

    # Help handling
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print_help()
        return 0

    # Subcommand handling
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(args) >= 1 and args[0].lower() == "version":
        return print_version()
    if len(args) >= 1 and args[0].lower() == "config":
        return run_config()
    if len(args) >= 1 and args[0].lower() == "mode":
        # Set or view confirmation mode
        CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        existing = parse_kv_file(CONFIG_FILE)
        current_mode = (
            existing.get("CONFIRM_MODE", os.environ.get("ADORABLE_CONFIRM_MODE", "auto")) or "auto"
        )
        if len(args) >= 2 and args[1].lower() in {"normal", "auto", "off"}:
            new_mode = args[1].lower()
            existing["CONFIRM_MODE"] = new_mode
            write_kv_file(CONFIG_FILE, existing)
            os.environ["ADORABLE_CONFIRM_MODE"] = new_mode
            console.print(f"✅ Confirm mode set to: {new_mode}")
            return 0
        else:
            console.print(f"Current confirm mode: {current_mode}")
            console.print("Use: adorable mode [normal|auto|off]")
            return 0

    # Ensure config and load env
    cfg = ensure_config_interactive()
    # If confirm mode not set in env, default to config or auto
    cm = cfg.get("CONFIRM_MODE", "").strip()
    if cm:
        os.environ.setdefault("ADORABLE_CONFIRM_MODE", cm)

    # Reduce Agno INFO logs (e.g., initial DB table creation) on first run
    configure_logging()

    # Todo-centric approach: manage project tasks via local todo.md

    # Build agent
    agent = build_agent()

    # Always start interactive chat mode
    return run_interactive(agent)


if __name__ == "__main__":
    raise SystemExit(main())


def apply_confirm_mode_to_agent(agent, mode: str) -> None:
    """Dynamically adjust requires_confirmation flags on the existing agent's tools.

    - normal: confirm python, shell, and save_file; others off
    - auto: confirm python and shell only; others off
    - off: all off
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
        elif mode == "off":
            # In off mode, still pause Python/Shell to allow hard-bans at confirmation layer, then auto-confirm.
            target_true = set().union(python_names, shell_names)

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
