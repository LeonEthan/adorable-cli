from __future__ import annotations

from typer.testing import CliRunner


def test_kb_check_pgvector_requires_dsn() -> None:
    from adorable_cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["kb", "check", "--backend", "pgvector"])
    assert result.exit_code != 0
    assert "requires a DSN" in result.output
