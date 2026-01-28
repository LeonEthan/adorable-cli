from __future__ import annotations

from pathlib import Path

from agno.team import Team
from agno.tools.file import FileTools
from agno.tools.shell import ShellTools

from adorable_cli.agent.builder import build_component
from adorable_cli.agent.main_agent import create_adorable_agent
from adorable_cli.agent.policy import ToolPolicy
from adorable_cli import config as cfg
from adorable_cli.settings import settings


def test_build_component_returns_team(tmp_path: Path, monkeypatch) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "config_path", tmp_path)

    component = build_component(team="coding")
    assert isinstance(component, Team)
    assert len(component.members) == 3


def test_build_component_loads_yaml_team(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "config_path", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path)

    teams_dir = tmp_path / "teams"
    teams_dir.mkdir(parents=True)
    (teams_dir / "custom.yaml").write_text(
        "name: custom\nagents:\n  - planner\n  - coder\n",
        encoding="utf-8",
    )

    component = build_component(team="custom")
    assert isinstance(component, Team)
    assert component.id == "custom"
    assert len(component.members) == 2


def test_planning_team_is_read_only_enforced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "config_path", tmp_path)

    agent = create_adorable_agent(tool_policy=ToolPolicy.from_mode("read-only"))
    tool_types = {type(t) for t in agent.tools}
    assert ShellTools not in tool_types

    file_tools = [t for t in agent.tools if isinstance(t, FileTools)]
    assert file_tools
    functions = getattr(file_tools[0], "functions", {})
    assert "save_file" not in functions
