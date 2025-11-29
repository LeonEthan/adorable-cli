import os
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.text import Text

# Load .env file if present
load_dotenv()

from adorable_cli.agent.builder import build_agent, configure_logging
from adorable_cli.config import (CONFIG_FILE, CONFIG_PATH,
                                 ensure_config_interactive, parse_kv_file,
                                 run_config, write_kv_file)
from adorable_cli.console import configure_console, console
from adorable_cli.ui.interactive import print_version, run_interactive

app = typer.Typer(add_completion=False)


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

    configure_console(plain)

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
        console.print(f"Confirm mode set to: {new_mode}", style="success")
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
