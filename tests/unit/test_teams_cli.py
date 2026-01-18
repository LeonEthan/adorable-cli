from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from adorable_cli import config as cfg
from adorable_cli.main import app


def test_teams_list_includes_builtin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config")
    monkeypatch.setattr(cfg, "CONFIG_JSON_FILE", tmp_path / "config.json")
    monkeypatch.setattr(cfg, "MEM_DB_PATH", tmp_path / "memory.db")

    runner = CliRunner()
    result = runner.invoke(app, ["teams", "list"])
    assert result.exit_code == 0
    assert "coding" in result.stdout
    assert "research" in result.stdout
    assert "planning" in result.stdout


def test_teams_list_marks_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config")
    monkeypatch.setattr(cfg, "CONFIG_JSON_FILE", tmp_path / "config.json")
    monkeypatch.setattr(cfg, "MEM_DB_PATH", tmp_path / "memory.db")

    teams_dir = tmp_path / "teams"
    teams_dir.mkdir(parents=True)
    (teams_dir / "custom.yaml").write_text("name: custom\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["teams", "list"])
    assert result.exit_code == 0
    assert "custom\tconfigured" in result.stdout

