import os
from pathlib import Path

from rich.panel import Panel
from rich.text import Text

from adorable_cli.console import console

CONFIG_PATH = Path.home() / ".adorable"
CONFIG_FILE = CONFIG_PATH / "config"
MEM_DB_PATH = CONFIG_PATH / "memory.db"


def sanitize(val: str) -> str:
    return val.strip().strip('"').strip("'").strip("`")


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
    vlm_model_id = cfg.get("VLM_MODEL_ID", "")
    confirm_mode = cfg.get("CONFIRM_MODE", "")
    if api_key:
        os.environ["API_KEY"] = api_key
        os.environ["OPENAI_API_KEY"] = api_key
    if base_url:
        os.environ["BASE_URL"] = base_url
        # Common env var name used by OpenAI clients
        os.environ["OPENAI_BASE_URL"] = base_url
    model_id = cfg.get("MODEL_ID", "")
    if model_id:
        os.environ["DEEPAGENTS_MODEL_ID"] = model_id
    if vlm_model_id:
        os.environ["DEEPAGENTS_VLM_MODEL_ID"] = vlm_model_id
    if confirm_mode:
        os.environ["DEEPAGENTS_CONFIRM_MODE"] = confirm_mode


def ensure_config_interactive() -> dict[str, str]:
    # Ensure configuration directory exists and read existing config if present
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    cfg: dict[str, str] = {}
    if CONFIG_FILE.exists():
        cfg = parse_kv_file(CONFIG_FILE)

    # Three variables are required: API_KEY, BASE_URL, MODEL_ID
    # One optional variable: VLM_MODEL_ID (for vision language model)
    required_keys = ["API_KEY", "BASE_URL", "MODEL_ID"]
    missing = [k for k in required_keys if not cfg.get(k, "").strip()]

    if missing:
        setup_message = """[warning]Configuration Setup[/warning]

[tip]Required:[/tip]
• API_KEY
• BASE_URL
• MODEL_ID

[tip]Optional:[/tip]
• VLM_MODEL_ID (for image understanding, defaults to MODEL_ID)
• FAST_MODEL_ID (for session summaries, defaults to MODEL_ID)"""

        console.print(
            Panel(
                Text.from_markup(setup_message),
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
        console.print(f"Configuration saved to {CONFIG_FILE}", style="success")

    # Load configuration into environment variables
    load_env_from_config(cfg)
    return cfg


def load_config_silent() -> None:
    """Load configuration from file if it exists, without prompting."""
    if CONFIG_FILE.exists():
        cfg = parse_kv_file(CONFIG_FILE)
        load_env_from_config(cfg)


def run_config() -> int:
    console.print(
        Panel(
            "Configure API_KEY, BASE_URL, MODEL_ID, VLM_MODEL_ID, FAST_MODEL_ID",
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
    current_vlm_model = existing.get("VLM_MODEL_ID", "")
    current_fast_model = existing.get("FAST_MODEL_ID", "")

    console.print(Text(f"Current API_KEY: {current_key or '(empty)'}", style="info"))
    api_key = input("Enter new API_KEY (leave blank to keep): ")
    console.print(Text(f"Current BASE_URL: {current_url or '(empty)'}", style="info"))
    base_url = input("Enter new BASE_URL (leave blank to keep): ")
    console.print(Text(f"Current MODEL_ID: {current_model or '(empty)'}", style="info"))
    model_id = input("Enter new MODEL_ID (leave blank to keep): ")
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
    if vlm_model_id.strip():
        new_cfg["VLM_MODEL_ID"] = sanitize(vlm_model_id)
    if fast_model_id.strip():
        new_cfg["FAST_MODEL_ID"] = sanitize(fast_model_id)

    write_kv_file(CONFIG_FILE, new_cfg)
    load_env_from_config(new_cfg)
    console.print(f"Configuration saved to {CONFIG_FILE}", style="success")
    return 0
