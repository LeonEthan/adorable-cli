from __future__ import annotations

from pathlib import Path

from agno.team import Team

from adorable_cli.agent.builder import build_component
from adorable_cli.settings import settings


def test_build_component_returns_team(tmp_path: Path, monkeypatch) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "config_path", tmp_path)

    component = build_component(team="coding")
    assert isinstance(component, Team)
    assert len(component.members) == 3

