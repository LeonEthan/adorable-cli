from __future__ import annotations

import asyncio

import pytest

from adorable_cli.ui import interactive


class _Tool:
    async def connect(self, *, force: bool = False):
        raise TimeoutError("boom")


@pytest.mark.asyncio
async def test_pin_mcp_tools_is_nonfatal_on_connect_failure(monkeypatch) -> None:
    monkeypatch.delenv("ADORABLE_DISABLE_MCP", raising=False)
    monkeypatch.setenv("ADORABLE_MCP_PIN_ON_STARTUP", "1")
    monkeypatch.setenv("ADORABLE_MCP_CONNECT_TIMEOUT", "0.01")

    monkeypatch.setattr(interactive, "_is_mcp_tool", lambda _obj: True)
    agent = type("A", (), {"tools": [_Tool()]})()

    pinned = await interactive._pin_mcp_tools_to_current_task(agent)  # noqa: SLF001
    assert pinned == []


@pytest.mark.asyncio
async def test_pin_mcp_tools_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ADORABLE_DISABLE_MCP", "1")
    monkeypatch.setenv("ADORABLE_MCP_PIN_ON_STARTUP", "1")
    monkeypatch.setattr(interactive, "_is_mcp_tool", lambda _obj: True)
    agent = type("A", (), {"tools": [_Tool()]})()

    pinned = await interactive._pin_mcp_tools_to_current_task(agent)  # noqa: SLF001
    assert pinned == []
