import os
import json
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.text import Text

from adorable_cli.console import console

CONFIG_PATH = Path(os.environ.get("ADORABLE_HOME", Path.home() / ".adorable"))
CONFIG_FILE = CONFIG_PATH / "config"
CONFIG_JSON_FILE = CONFIG_PATH / "config.json"
WORKFLOWS_DIR = CONFIG_PATH / "workflows"
MEM_DB_PATH = CONFIG_PATH / "memory.db"
USER_DIR_NAMES = ("teams", "workflows", "skills", "tools", "commands")


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


def parse_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def write_json_file(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _get_nested(cfg: dict[str, Any], path: list[str]) -> Any:
    cur: Any = cfg
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def normalize_config(cfg: dict[str, Any]) -> dict[str, str]:
    def pick(*candidates: Any) -> str:
        for c in candidates:
            if c is None:
                continue
            if isinstance(c, str) and c.strip():
                return sanitize(c)
            if isinstance(c, (int, float)):
                return str(c)
        return ""

    return {
        "API_KEY": pick(cfg.get("API_KEY"), _get_nested(cfg, ["openai", "api_key"])),
        "BASE_URL": pick(cfg.get("BASE_URL"), _get_nested(cfg, ["openai", "base_url"])),
        "MODEL_ID": pick(cfg.get("MODEL_ID"), _get_nested(cfg, ["models", "default"])),
        "VLM_MODEL_ID": pick(cfg.get("VLM_MODEL_ID"), _get_nested(cfg, ["models", "vlm"])),
        "FAST_MODEL_ID": pick(cfg.get("FAST_MODEL_ID"), _get_nested(cfg, ["models", "fast"])),
        "CONFIRM_MODE": pick(cfg.get("CONFIRM_MODE"), cfg.get("confirm_mode")),
        "SERVER_HOST": pick(cfg.get("SERVER_HOST"), _get_nested(cfg, ["server", "host"])),
        "SERVER_PORT": pick(cfg.get("SERVER_PORT"), _get_nested(cfg, ["server", "port"])),
        "DB_PATH": pick(cfg.get("DB_PATH"), _get_nested(cfg, ["db", "path"])),
        "KB_BACKEND": pick(cfg.get("KB_BACKEND"), _get_nested(cfg, ["knowledge", "backend"])),
        "KB_PGVECTOR_DSN": pick(
            cfg.get("KB_PGVECTOR_DSN"), _get_nested(cfg, ["knowledge", "pgvector", "dsn"])
        ),
        "KB_PGVECTOR_TABLE": pick(
            cfg.get("KB_PGVECTOR_TABLE"), _get_nested(cfg, ["knowledge", "pgvector", "table"])
        ),
    }


def materialize_json_config(flat_cfg: dict[str, str]) -> dict[str, Any]:
    def parse_int(val: str, default: int) -> int:
        try:
            return int(val)
        except Exception:
            return default

    return {
        "openai": {
            "api_key": flat_cfg.get("API_KEY", ""),
            "base_url": flat_cfg.get("BASE_URL", ""),
        },
        "models": {
            "default": flat_cfg.get("MODEL_ID", ""),
            "fast": flat_cfg.get("FAST_MODEL_ID", ""),
            "vlm": flat_cfg.get("VLM_MODEL_ID", ""),
        },
        "confirm_mode": flat_cfg.get("CONFIRM_MODE", ""),
        "server": {
            "host": flat_cfg.get("SERVER_HOST", "") or "0.0.0.0",
            "port": parse_int(flat_cfg.get("SERVER_PORT", ""), 7777),
        },
        "db": {
            "path": flat_cfg.get("DB_PATH", ""),
        },
        "knowledge": {
            "backend": flat_cfg.get("KB_BACKEND", ""),
            "pgvector": {
                "dsn": flat_cfg.get("KB_PGVECTOR_DSN", ""),
                "table": flat_cfg.get("KB_PGVECTOR_TABLE", ""),
            },
        },
    }


def read_config() -> dict[str, str]:
    if CONFIG_JSON_FILE.exists():
        raw = parse_json_file(CONFIG_JSON_FILE)
        if raw:
            return normalize_config(raw)
    return parse_kv_file(CONFIG_FILE)


def ensure_user_layout() -> None:
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    for name in USER_DIR_NAMES:
        (CONFIG_PATH / name).mkdir(parents=True, exist_ok=True)


def write_config(flat_cfg: dict[str, str]) -> None:
    ensure_user_layout()
    write_json_file(CONFIG_JSON_FILE, materialize_json_config(flat_cfg))
    write_kv_file(CONFIG_FILE, flat_cfg)


def load_env_from_config(cfg: dict[str, str]) -> None:
    # Persist requested env vars
    api_key = cfg.get("API_KEY", "")
    base_url = cfg.get("BASE_URL", "")
    fast_model_id = cfg.get("FAST_MODEL_ID", "")
    vlm_model_id = cfg.get("VLM_MODEL_ID", "")
    confirm_mode = cfg.get("CONFIRM_MODE", "")
    server_host = cfg.get("SERVER_HOST", "")
    server_port = cfg.get("SERVER_PORT", "")
    db_path = cfg.get("DB_PATH", "")
    kb_backend = cfg.get("KB_BACKEND", "")
    kb_pgvector_dsn = cfg.get("KB_PGVECTOR_DSN", "")
    kb_pgvector_table = cfg.get("KB_PGVECTOR_TABLE", "")
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
    if fast_model_id:
        os.environ["DEEPAGENTS_FAST_MODEL_ID"] = fast_model_id
    if confirm_mode:
        os.environ["DEEPAGENTS_CONFIRM_MODE"] = confirm_mode
    if server_host:
        os.environ["ADORABLE_SERVER_HOST"] = server_host
        os.environ.setdefault("SERVER_HOST", server_host)
    if server_port:
        os.environ["ADORABLE_SERVER_PORT"] = server_port
        os.environ.setdefault("SERVER_PORT", server_port)
    if db_path:
        os.environ["ADORABLE_DB_PATH"] = db_path
        os.environ.setdefault("DB_PATH", db_path)
    if kb_backend:
        os.environ["ADORABLE_KB_BACKEND"] = kb_backend
        os.environ.setdefault("KB_BACKEND", kb_backend)
    if kb_pgvector_dsn:
        os.environ["ADORABLE_KB_PGVECTOR_DSN"] = kb_pgvector_dsn
        os.environ.setdefault("KB_PGVECTOR_DSN", kb_pgvector_dsn)
    if kb_pgvector_table:
        os.environ["ADORABLE_KB_PGVECTOR_TABLE"] = kb_pgvector_table
        os.environ.setdefault("KB_PGVECTOR_TABLE", kb_pgvector_table)


def ensure_config_interactive() -> dict[str, str]:
    # Ensure configuration directory exists and read existing config if present
    ensure_user_layout()
    cfg = read_config()

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

        write_config(cfg)
        console.print(f"Configuration saved to {CONFIG_JSON_FILE}", style="success")

    # Load configuration into environment variables
    load_env_from_config(cfg)
    return cfg


def load_config_silent() -> None:
    """Load configuration from file if it exists, without prompting."""
    if CONFIG_JSON_FILE.exists() or CONFIG_FILE.exists():
        cfg = read_config()
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
    ensure_user_layout()
    existing = read_config()
    current_key = existing.get("API_KEY", "")
    current_url = existing.get("BASE_URL", "")
    current_model = existing.get("MODEL_ID", "")
    current_vlm_model = existing.get("VLM_MODEL_ID", "")
    current_fast_model = existing.get("FAST_MODEL_ID", "")
    current_server_host = existing.get("SERVER_HOST", "")
    current_server_port = existing.get("SERVER_PORT", "")

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

    console.print(
        Text(f"Current SERVER_HOST: {current_server_host or '(default: 0.0.0.0)'}", style="info")
    )
    server_host = input("Enter new SERVER_HOST (leave blank to keep): ")
    console.print(
        Text(f"Current SERVER_PORT: {current_server_port or '(default: 7777)'}", style="info")
    )
    server_port = input("Enter new SERVER_PORT (leave blank to keep): ")

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
    if server_host.strip():
        new_cfg["SERVER_HOST"] = sanitize(server_host)
    if server_port.strip():
        new_cfg["SERVER_PORT"] = sanitize(server_port)

    write_config(new_cfg)
    load_env_from_config(new_cfg)
    console.print(f"Configuration saved to {CONFIG_JSON_FILE}", style="success")
    return 0
