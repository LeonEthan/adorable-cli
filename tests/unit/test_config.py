from __future__ import annotations

from adorable_cli.config import materialize_json_config, normalize_config


def test_normalize_config_db_and_kb() -> None:
    cfg = {
        "db": {"path": "/tmp/adorable.db"},
        "knowledge": {
            "backend": "pgvector",
            "pgvector": {"dsn": "postgres://user:pass@localhost:5432/db", "table": "kb"},
        },
    }

    flat = normalize_config(cfg)
    assert flat["DB_PATH"] == "/tmp/adorable.db"
    assert flat["KB_BACKEND"] == "pgvector"
    assert flat["KB_PGVECTOR_DSN"] == "postgres://user:pass@localhost:5432/db"
    assert flat["KB_PGVECTOR_TABLE"] == "kb"


def test_materialize_config_db_and_kb() -> None:
    flat = {
        "DB_PATH": "/tmp/adorable.db",
        "KB_BACKEND": "pgvector",
        "KB_PGVECTOR_DSN": "postgres://user:pass@localhost:5432/db",
        "KB_PGVECTOR_TABLE": "kb",
    }

    data = materialize_json_config(flat)
    assert data["db"]["path"] == "/tmp/adorable.db"
    assert data["knowledge"]["backend"] == "pgvector"
    assert data["knowledge"]["pgvector"]["dsn"] == "postgres://user:pass@localhost:5432/db"
    assert data["knowledge"]["pgvector"]["table"] == "kb"
