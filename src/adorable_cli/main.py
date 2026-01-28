import asyncio
import os
from typing import Optional

import httpx
import typer

from adorable_cli.agent.builder import build_component, configure_logging
from adorable_cli.config import ensure_config_interactive, load_config_silent, run_config
from adorable_cli.console import configure_console
from adorable_cli.settings import reload_settings, settings
from adorable_cli.ui.interactive import print_version, run_interactive

app = typer.Typer(add_completion=False)
teams_app = typer.Typer(add_completion=False)
app.add_typer(teams_app, name="teams")
workflows_app = typer.Typer(add_completion=False)
workflow_app = typer.Typer(add_completion=False)
app.add_typer(workflows_app, name="workflows")
app.add_typer(workflow_app, name="workflow")

kb_app = typer.Typer(add_completion=False)
app.add_typer(kb_app, name="kb")

eval_app = typer.Typer(add_completion=False)
app.add_typer(eval_app, name="eval")

db_app = typer.Typer(add_completion=False)
app.add_typer(db_app, name="db")


@kb_app.command("create")
def kb_create(
    name: str = typer.Argument(..., help="Name of the knowledge base"),
    path: str = typer.Argument(..., help="Path to directory containing documents"),
) -> None:
    from pathlib import Path

    from adorable_cli.knowledge.manager import KnowledgeManager

    manager = KnowledgeManager(name=name)
    print(f"Indexing documents from {path} into '{name}'...")
    try:
        count = manager.load_directory(Path(path))
        print(f"Successfully indexed {count} documents.")
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


@kb_app.command("search")
def kb_search(
    name: str = typer.Argument(..., help="Name of the knowledge base"),
    query: str = typer.Argument(..., help="Query string"),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of results"),
) -> None:
    from adorable_cli.knowledge.manager import KnowledgeManager

    manager = KnowledgeManager(name=name)
    # Check existence by checking if dir exists
    if not manager.kb_path.exists():
        print(f"Knowledge base '{name}' does not exist.")
        raise typer.Exit(1)

    print(f"Searching '{name}' for: {query}")
    try:
        results = manager.search(query, num_results=limit)
    except Exception as e:
        print(f"Error during search: {e}")
        raise typer.Exit(1)

    if not results:
        print("No results found.")
    else:
        for i, res in enumerate(results, 1):
            print(f"\n--- Result {i} (Score: {res.get('score', 0.0):.4f}) ---")
            print(f"Source: {res.get('name', 'unknown')}")
            content = res.get("content", "")
            # Truncate content for display
            display_content = content[:500] + "..." if len(content) > 500 else content
            print(display_content)


@kb_app.command("update")
def kb_update(
    name: str = typer.Argument(..., help="Name of the knowledge base"),
    path: str = typer.Argument(..., help="Path to directory to re-index"),
) -> None:
    # Same as create for now, as upsert is True
    kb_create(name, path)


@kb_app.command("check")
def kb_check(
    name: str = typer.Option("default", "--name", help="Name of the knowledge base"),
    backend: Optional[str] = typer.Option(None, "--backend", help="Backend: lancedb or pgvector"),
    pgvector_dsn: Optional[str] = typer.Option(
        None, "--pgvector-dsn", help="pgvector DSN, e.g. postgres://user:pass@host/db"
    ),
    pgvector_table: Optional[str] = typer.Option(None, "--pgvector-table", help="pgvector table name"),
) -> None:
    from adorable_cli.knowledge.manager import KnowledgeManager
    from adorable_cli.settings import reload_settings

    if backend:
        os.environ["ADORABLE_KB_BACKEND"] = backend
    if pgvector_dsn:
        os.environ["ADORABLE_KB_PGVECTOR_DSN"] = pgvector_dsn
    if pgvector_table:
        os.environ["ADORABLE_KB_PGVECTOR_TABLE"] = pgvector_table

    reload_settings()

    try:
        KnowledgeManager(name=name)
        print("Knowledge backend initialized successfully.")
    except Exception as e:
        print(f"Knowledge backend check failed: {e}")
        raise typer.Exit(1)


@eval_app.command("run")
def eval_run(
    suite_path: str = typer.Argument(..., help="Path to eval suite YAML file"),
    team: Optional[str] = typer.Option(None, "--team"),
    output: Optional[str] = typer.Option(None, "--output", help="Path to save report"),
) -> None:
    from pathlib import Path
    from adorable_cli.evals.runner import EvalRunner
    
    runner = EvalRunner()
    path = Path(suite_path)
    if not path.exists():
        print(f"Eval suite not found: {path}")
        raise typer.Exit(1)
        
    suite = runner.load_suite(path)
    print(f"Running eval suite: {suite.name} ({len(suite.cases)} cases)")
    
    async def run():
        report = await runner.run_suite(suite, team=team)
        return report

    report = _run_async(run())
    
    print(f"\nResults: {report.passed}/{report.total} passed")
    for res in report.results:
        status = "PASS" if res.success else "FAIL"
        print(f"[{status}] {res.case.input[:50]}...")
        if not res.success:
            print(f"  Expected: {res.case.expected or res.case.expected_contains}")
            print(f"  Actual:   {res.actual_output}")
            if res.error:
                print(f"  Error:    {res.error}")

    if output:
        with open(output, "w") as f:
            f.write(report.json(indent=2))
        print(f"Report saved to {output}")
        
    if report.failed > 0:
        raise typer.Exit(1)


@eval_app.command("report")
def eval_report(
    path: str = typer.Argument(..., help="Path to report JSON file"),
) -> None:
    import json
    from pathlib import Path
    
    p = Path(path)
    if not p.exists():
        print(f"Report not found: {path}")
        raise typer.Exit(1)
        
    with open(p, "r") as f:
        data = json.load(f)
        
    print(f"Report: {data.get('suite_name', 'Unknown')}")
    print(f"Score: {data.get('passed')}/{data.get('total')}")


@db_app.command("migrate")
def db_migrate() -> None:
    from adorable_cli.db.migrations import run_migrations
    run_migrations()


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
    team: Optional[str] = typer.Option(None, "--team"),
    debug: bool = typer.Option(False, "--debug"),
    debug_level: Optional[int] = typer.Option(None, "--debug-level"),
    plain: bool = typer.Option(False, "--plain"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
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
        try:
            component = build_component(team=team)
        except ValueError as e:
            raise typer.BadParameter(str(e)) from e
        code = _run_async(run_interactive(component, session_id=session_id, user_id=user_id))
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
def chat(
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    team: Optional[str] = typer.Option(None, "--team"),
) -> None:
    ensure_config_interactive()
    reload_settings()
    configure_logging()
    try:
        component = build_component(team=team)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    code = _run_async(run_interactive(component, session_id=session_id, user_id=user_id))
    raise typer.Exit(code)


@app.command()
def serve(
    host: Optional[str] = typer.Option(None, "--host"),
    port: Optional[int] = typer.Option(None, "--port"),
    reload: bool = typer.Option(False, "--reload"),
    check: bool = typer.Option(False, "--check"),
) -> None:
    ensure_config_interactive()
    reload_settings()
    configure_logging()

    effective_host = host or settings.server_host
    effective_port = port or settings.server_port

    if host:
        os.environ["ADORABLE_SERVER_HOST"] = host
    if port is not None:
        os.environ["ADORABLE_SERVER_PORT"] = str(port)

    if check:
        from adorable_cli.os.server import create_agent_os

        agent_os = create_agent_os()
        app = agent_os.get_app()

        async def run_check() -> int:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://adorable.local",
            ) as client:
                resp = await client.get("/status")
            return resp.status_code

        status = _run_async(run_check())
        raise typer.Exit(0 if status == 200 else 1)

    try:
        import uvicorn
    except ImportError as e:
        raise RuntimeError(
            "uvicorn is required for `ador serve`. Install it with: pip install uvicorn"
        ) from e

    if reload:
        uvicorn.run(
            "adorable_cli.os.server:app",
            host=effective_host,
            port=effective_port,
            reload=True,
        )
        raise typer.Exit(0)

    from adorable_cli.os.server import create_agent_os

    agent_os = create_agent_os()
    uvicorn.run(
        agent_os.get_app(),
        host=effective_host,
        port=effective_port,
    )
    raise typer.Exit(0)


@app.command()
def attach(
    url: str = typer.Argument(...),
    agent_id: Optional[str] = typer.Option(None, "--agent-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    token: Optional[str] = typer.Option(None, "--token"),
    list_sessions: bool = typer.Option(False, "--list-sessions"),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    async def run_attach() -> int:
        from agno.client import AgentOSClient
        from agno.db.base import SessionType

        from adorable_cli.os.remote_agent import RemoteAgent

        base_url = url.strip()
        if "://" not in base_url:
            base_url = f"http://{base_url}"

        headers = {"Authorization": f"Bearer {token}"} if token else None
        client = AgentOSClient(base_url=base_url)

        config = await client.aget_config(headers=headers)
        effective_agent_id = agent_id or (config.agents[0].id if config.agents else None)
        if effective_agent_id is None:
            raise RuntimeError("No agents available on the remote AgentOS instance.")

        if list_sessions:
            sessions = await client.get_sessions(
                session_type=SessionType.AGENT,
                component_id=effective_agent_id,
                user_id=user_id,
                limit=limit,
                headers=headers,
            )
            for s in sessions.data:
                name = getattr(s, "session_name", None) or ""
                suffix = f"  {name}" if name else ""
                print(f"{s.session_id}{suffix}")
            return 0

        effective_user_id = user_id or os.environ.get("ADORABLE_USER_ID") or os.environ.get("USER")
        remote_agent = RemoteAgent(
            client=client,
            agent_id=effective_agent_id,
            session_id=session_id,
            user_id=effective_user_id,
            headers=headers,
        )

        code = await run_interactive(remote_agent)
        return code

    code = _run_async(run_attach())
    raise typer.Exit(code)


@teams_app.command("list")
def teams_list() -> None:
    from adorable_cli.config import CONFIG_PATH, ensure_user_layout
    from adorable_cli.teams.builder import list_builtin_team_ids, list_configured_team_ids, list_team_ids

    ensure_user_layout()
    builtin = set(list_builtin_team_ids())
    configured = set(list_configured_team_ids(config_path=CONFIG_PATH))
    available = list_team_ids(config_path=CONFIG_PATH)

    for team_id in available:
        label = "configured" if team_id in configured else "builtin" if team_id in builtin else "unknown"
        print(f"{team_id}\t{label}")


@workflows_app.command("list")
def workflows_list() -> None:
    from adorable_cli.config import ensure_user_layout
    from adorable_cli.workflows.registry import list_workflows

    ensure_user_layout()
    for wf in list_workflows():
        source = "builtin" if wf.workflow_id in ("research", "code-review") else "custom"
        print(f"{wf.workflow_id}\t{source}\t{wf.description}")


@workflow_app.command("run")
def workflow_run(
    workflow_id: str = typer.Argument(...),
    input_text: str = typer.Option("", "--input"),
    offline: bool = typer.Option(False, "--offline"),
    diff_file: Optional[str] = typer.Option(None, "--diff-file"),
    run_tests: bool = typer.Option(True, "--run-tests/--no-run-tests"),
    tests_cmd: str = typer.Option("pytest -q", "--tests-cmd"),
    timeout_s: float = typer.Option(900.0, "--timeout-s"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    team: Optional[str] = typer.Option(None, "--team"),
) -> None:
    from pathlib import Path

    from adorable_cli.agent.builder import build_component, configure_logging
    from adorable_cli.config import ensure_config_interactive
    from adorable_cli.settings import reload_settings
    from adorable_cli.workflows.registry import (
        UnknownWorkflowError,
        get_workflow,
    )

    try:
        wf = get_workflow(workflow_id)
    except UnknownWorkflowError as e:
        raise typer.BadParameter(str(e)) from e

    async def run_selected() -> int:
        component = None
        if not offline and wf.requires_component:
            ensure_config_interactive()
            reload_settings()
            configure_logging()
            component = build_component(team=team)

        result = await wf.run(
            input_text=input_text,
            component=component,
            offline=offline,
            session_id=session_id,
            user_id=user_id,
            diff_file=Path(diff_file) if diff_file else None,
            run_tests=run_tests,
            tests_cmd=tests_cmd,
            timeout_s=timeout_s,
        )

        print(result.output, end="" if result.output.endswith("\n") else "\n")
        return 0

    code = _run_async(run_selected())
    raise typer.Exit(code)


def main() -> int:
    app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
