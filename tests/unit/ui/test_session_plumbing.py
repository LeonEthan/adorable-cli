from __future__ import annotations

from types import SimpleNamespace

import pytest


class _DummyRenderer:
    def __init__(self) -> None:
        self.final = ""

    def start_stream(self) -> None:
        return None

    def update_content(self, delta: str) -> None:
        return None

    def set_final_content(self, content: str) -> None:
        self.final = content

    def render_tool_call(self, event) -> None:
        return None

    def pause_stream(self) -> None:
        return None

    def resume_stream(self) -> None:
        return None

    def finish_stream(self) -> None:
        return None

    def get_final_text(self) -> str:
        return self.final


class _DummyAgent:
    def __init__(self) -> None:
        self.arun_calls: list[dict] = []
        self.continue_calls: list[dict] = []

    async def arun(self, user_input: str, **kwargs):
        self.arun_calls.append(kwargs)

        async def gen():
            yield SimpleNamespace(is_paused=True, run_id="r1", tools=[])

        return gen()

    async def acontinue_run(self, **kwargs):
        self.continue_calls.append(kwargs)

        async def gen():
            yield SimpleNamespace(event="RunCompleted", content="done", metrics=None)

        return gen()


@pytest.mark.asyncio
async def test_process_agent_stream_passes_session_and_user():
    from rich.console import Console

    from adorable_cli.ui.interactive import process_agent_stream

    agent = _DummyAgent()
    renderer = _DummyRenderer()
    console = Console(file=None, force_terminal=False, color_system=None, width=80)

    final_text, _, _, _ = await process_agent_stream(
        agent,
        "hi",
        renderer,
        console,
        session_id="s1",
        user_id="u1",
    )

    assert final_text == "done"
    assert agent.arun_calls[0]["session_id"] == "s1"
    assert agent.arun_calls[0]["user_id"] == "u1"
    assert agent.continue_calls[0]["session_id"] == "s1"
    assert agent.continue_calls[0]["user_id"] == "u1"

