import asyncio
import logging
import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Dict

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAILike
from agno.tools.calculator import CalculatorTools
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.file import FileTools
from agno.tools.memory import MemoryTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.tavily import TavilyTools
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from adorable_cli.prompt import MAIN_AGENT_DESCRIPTION, MAIN_AGENT_INSTRUCTIONS

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
        logging.getLogger("agno").setLevel(logging.WARNING)
        logging.getLogger("agno.db").setLevel(logging.WARNING)
        logging.getLogger("agno.db.sqlite").setLevel(logging.WARNING)
    except Exception:
        # Non-fatal if logging configuration fails
        pass


def parse_kv_file(path: Path) -> Dict[str, str]:
    cfg: Dict[str, str] = {}
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


def write_kv_file(path: Path, data: Dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in data.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_env_from_config(cfg: Dict[str, str]) -> None:
    # Persist requested env vars
    api_key = cfg.get("API_KEY", "")
    base_url = cfg.get("BASE_URL", "")
    tavily_key = cfg.get("TAVILY_API_KEY", "")
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


def ensure_config_interactive() -> Dict[str, str]:
    # Ensure configuration directory exists and read existing config if present
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    cfg: Dict[str, str] = {}
    if CONFIG_FILE.exists():
        cfg = parse_kv_file(CONFIG_FILE)

    # Four variables are required: API_KEY, BASE_URL, MODEL_ID, TAVILY_API_KEY
    required_keys = ["API_KEY", "BASE_URL", "MODEL_ID", "TAVILY_API_KEY"]
    missing = [k for k in required_keys if not cfg.get(k, "").strip()]

    if missing:
        console.print(
            Panel(
                "🔧 Initial or missing configuration: please provide four required variables: API_KEY, BASE_URL, MODEL_ID, TAVILY_API_KEY.",
                title="Adorable Setup",
                border_style="yellow",
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
    model_id = os.environ.get("ADORABLE_MODEL_ID", "gpt-4o-mini")

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
        # Local file operations limited to the launch directory
        FileTools(base_dir=Path.cwd(), all=True),
        # User memory tools
        MemoryTools(db=db),
    ]

    main_agent = Agent(
        name="adorable",
        model=OpenAILike(
            id=model_id,
            api_key=api_key,
            base_url=base_url,
            max_tokens=32000,
            extra_body={"thinking": {"type": "disabled"}},
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
    return main_agent


def print_help():
    help_text = Text()
    help_text.append("Adorable CLI - Agno-based command-line assistant\n", style="bold cyan")
    help_text.append("\nUsage:\n", style="bold")
    help_text.append("  adorable               Enter interactive chat mode\n")
    help_text.append(
        "  adorable config        Configure API_KEY, BASE_URL, TAVILY_API_KEY and MODEL_ID\n"
    )
    help_text.append("  adorable --help        Show help information\n")
    help_text.append("\nExamples:\n", style="bold")
    help_text.append("  adorable\n")
    help_text.append("  adorable config\n")
    help_text.append("\nNotes:\n", style="bold")
    help_text.append(
        "  - On first run, you must set four required variables: API_KEY, BASE_URL, MODEL_ID, TAVILY_API_KEY; configuration is stored at ~/.adorable/config\n"
    )
    help_text.append("  - MODEL_ID can be set via `adorable config` (e.g., glm-4-flash)\n")
    help_text.append(
        "  - TAVILY_API_KEY is set via `adorable config` to enable web search (Tavily)\n"
    )
    help_text.append("  - Input history is supported; use up/down arrows to recall\n")
    console.print(Panel(help_text, title="Help", border_style="blue"))


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
            "Configure API_KEY, BASE_URL, MODEL_ID, TAVILY_API_KEY",
            title="Adorable Config",
            border_style="yellow",
        )
    )
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    existing = parse_kv_file(CONFIG_FILE)
    current_key = existing.get("API_KEY", "")
    current_url = existing.get("BASE_URL", "")
    current_model = existing.get("MODEL_ID", "")
    current_tavily = existing.get("TAVILY_API_KEY", "")

    console.print(Text(f"Current API_KEY: {current_key or '(empty)'}", style="cyan"))
    api_key = input("Enter new API_KEY (leave blank to keep): ")
    console.print(Text(f"Current BASE_URL: {current_url or '(empty)'}", style="cyan"))
    base_url = input("Enter new BASE_URL (leave blank to keep): ")
    console.print(Text(f"Current MODEL_ID: {current_model or '(empty)'}", style="cyan"))
    model_id = input("Enter new MODEL_ID (leave blank to keep): ")
    console.print(Text(f"Current TAVILY_API_KEY: {current_tavily or '(empty)'}", style="cyan"))
    tavily_api_key = input("Enter new TAVILY_API_KEY (leave blank to keep): ")

    new_cfg = dict(existing)
    if api_key.strip():
        new_cfg["API_KEY"] = sanitize(api_key)
    if base_url.strip():
        new_cfg["BASE_URL"] = sanitize(base_url)
    if model_id.strip():
        new_cfg["MODEL_ID"] = sanitize(model_id)
    if tavily_api_key.strip():
        new_cfg["TAVILY_API_KEY"] = sanitize(tavily_api_key)

    write_kv_file(CONFIG_FILE, new_cfg)
    load_env_from_config(new_cfg)
    console.print(f"✅ Saved to {CONFIG_FILE}", style="green")
    return 0


async def run_interactive_async(agent) -> int:
    console.print(
        Panel(
            "🤖 Adorable started. Type exit or exit() to quit.",
            title="Adorable",
            border_style="green",
        )
    )
    await agent.acli_app(
        stream=True,
        markdown=True,
        exit_on=["exit", "exit()", "quit", "q", "bye"],
    )
    return 0


def run_interactive(agent) -> int:
    return asyncio.run(run_interactive_async(agent))


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

    # Ensure config and load env
    ensure_config_interactive()

    # Reduce Agno INFO logs (e.g., initial DB table creation) on first run
    configure_logging()

    # Todo-centric approach: manage project tasks via local todo.md

    # Build agent
    agent = build_agent()

    # Always start interactive chat mode
    return run_interactive(agent)


if __name__ == "__main__":
    raise SystemExit(main())
