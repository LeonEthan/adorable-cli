import asyncio
import os
from typing import Optional

import typer

from adorable_cli.agent.builder import build_agent, configure_logging
from adorable_cli.config import ensure_config_interactive, load_config_silent, run_config
from adorable_cli.console import configure_console
from adorable_cli.settings import reload_settings
from adorable_cli.ui.interactive import print_version, run_interactive

app = typer.Typer(add_completion=False)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        if hasattr(coro, "close"):
            coro.close()
        raise RuntimeError("Cannot start CLI loop from a running event loop")



@app.callback(invoke_without_command=True)
def app_entry(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(None, "--model"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    fast_model: Optional[str] = typer.Option(None, "--fast-model"),
    debug: bool = typer.Option(False, "--debug"),
    debug_level: Optional[int] = typer.Option(None, "--debug-level"),
    plain: bool = typer.Option(False, "--plain"),
) -> None:
    load_config_silent()

    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ.setdefault("API_KEY", api_key)
    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url
        os.environ.setdefault("BASE_URL", base_url)
    if model:
        os.environ["DEEPAGENTS_MODEL_ID"] = model
    if fast_model:
        os.environ["DEEPAGENTS_FAST_MODEL_ID"] = fast_model
    if debug:
        os.environ["AGNO_DEBUG"] = "1"
    if debug_level is not None:
        os.environ["AGNO_DEBUG_LEVEL"] = str(debug_level)

    configure_console(plain)

    if ctx.invoked_subcommand is None:
        ensure_config_interactive()
        reload_settings()
        configure_logging()
        agent = build_agent()
        code = _run_async(run_interactive(agent))
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
def chat() -> None:
    ensure_config_interactive()
    reload_settings()
    configure_logging()
    agent = build_agent()
    code = _run_async(run_interactive(agent))
    raise typer.Exit(code)


def main() -> int:
    app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
