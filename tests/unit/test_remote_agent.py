from __future__ import annotations

from types import SimpleNamespace

import pytest

from adorable_cli.os.remote_agent import RemoteAgent


class _DummyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run_agent_stream(self, **kwargs):
        self.calls.append(("run_agent_stream", kwargs))

        async def gen():
            yield SimpleNamespace(event="RunCompleted", content="ok", metrics=None)

        return gen()

    async def run_agent(self, **kwargs):
        self.calls.append(("run_agent", kwargs))
        return SimpleNamespace(content="ok")

    def continue_agent_run_stream(self, **kwargs):
        self.calls.append(("continue_agent_run_stream", kwargs))

        async def gen():
            yield SimpleNamespace(event="RunCompleted", content="ok", metrics=None)

        return gen()

    async def continue_agent_run(self, **kwargs):
        self.calls.append(("continue_agent_run", kwargs))
        return SimpleNamespace(content="ok")


@pytest.mark.asyncio
async def test_remote_agent_stream_overrides_session_and_user():
    client = _DummyClient()
    agent = RemoteAgent(client=client, agent_id="a1", session_id="s0", user_id="u0")

    stream = await agent.arun("hi", stream=True, session_id="s1", user_id="u1")
    async for _ in stream:
        break

    name, kwargs = client.calls[0]
    assert name == "run_agent_stream"
    assert kwargs["agent_id"] == "a1"
    assert kwargs["session_id"] == "s1"
    assert kwargs["user_id"] == "u1"


@pytest.mark.asyncio
async def test_remote_agent_continue_stream_passes_tools():
    from agno.models.response import ToolExecution

    client = _DummyClient()
    agent = RemoteAgent(client=client, agent_id="a1", session_id="s0", user_id="u0")

    tools = [ToolExecution(tool_call_id="call-1", result="ok")]
    stream = await agent.acontinue_run(run_id="r1", updated_tools=tools, stream=True)
    async for _ in stream:
        break

    name, kwargs = client.calls[0]
    assert name == "continue_agent_run_stream"
    assert kwargs["run_id"] == "r1"
    assert kwargs["tools"] == tools

