from __future__ import annotations

from fastapi import FastAPI

from agno.os import AgentOS

from adorable_cli.agent.builder import build_agent, configure_logging
from adorable_cli.config import load_config_silent
from adorable_cli.settings import reload_settings


def create_agent_os() -> AgentOS:
    load_config_silent()
    reload_settings()
    configure_logging()

    base_app = FastAPI(title="Adorable AgentOS")

    @base_app.get("/status")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    agent = build_agent()
    return AgentOS(agents=[agent], base_app=base_app)


agent_os = create_agent_os()
app = agent_os.get_app()
