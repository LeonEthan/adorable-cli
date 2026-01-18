from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from adorable_cli import config as cfg
from adorable_cli.main import app


def _patch_config_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config")
    monkeypatch.setattr(cfg, "CONFIG_JSON_FILE", tmp_path / "config.json")
    monkeypatch.setattr(cfg, "MEM_DB_PATH", tmp_path / "memory.db")


def test_workflows_list_includes_builtin(tmp_path: Path, monkeypatch) -> None:
    _patch_config_paths(tmp_path, monkeypatch)

    runner = CliRunner()
    result = runner.invoke(app, ["workflows", "list"])
    assert result.exit_code == 0
    assert "research" in result.stdout
    assert "code-review" in result.stdout


def test_workflow_run_research_offline(tmp_path: Path, monkeypatch) -> None:
    _patch_config_paths(tmp_path, monkeypatch)

    runner = CliRunner()
    result = runner.invoke(app, ["workflow", "run", "research", "--offline", "--input", "hello"])
    assert result.exit_code == 0
    assert "# Research Workflow" in result.stdout
    assert "## Search" in result.stdout
    assert "## Analysis" in result.stdout
    assert "## Answer" in result.stdout


def test_workflow_run_code_review_without_tests(tmp_path: Path, monkeypatch) -> None:
    _patch_config_paths(tmp_path, monkeypatch)

    diff = "\n".join(
        [
            "diff --git a/src/foo.py b/src/foo.py",
            "index 1111111..2222222 100644",
            "--- a/src/foo.py",
            "+++ b/src/foo.py",
            "@@ -1,1 +1,2 @@",
            "-print('a')",
            "+print('b')",
            "+print('c')",
        ]
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["workflow", "run", "code-review", "--input", diff, "--no-run-tests"],
    )
    assert result.exit_code == 0
    assert "# Code Review Report" in result.stdout
    assert "Files changed: 1" in result.stdout
    assert "Lines added: 2" in result.stdout
    assert "Lines removed: 1" in result.stdout

