from __future__ import annotations

from pathlib import Path

from adorable_cli.settings import Settings


def test_settings_db_path_env(monkeypatch) -> None:
    monkeypatch.setenv("ADORABLE_DB_PATH", "/tmp/adorable.db")
    settings = Settings.from_env()
    assert settings.db_path == Path("/tmp/adorable.db")
    assert settings.mem_db_path == Path("/tmp/adorable.db")


def test_settings_kb_backend_env(monkeypatch) -> None:
    monkeypatch.setenv("ADORABLE_KB_BACKEND", "pgvector")
    monkeypatch.setenv("ADORABLE_KB_PGVECTOR_DSN", "postgres://user:pass@localhost:5432/db")
    settings = Settings.from_env()
    assert settings.kb_backend == "pgvector"
    assert settings.kb_pgvector_dsn == "postgres://user:pass@localhost:5432/db"
